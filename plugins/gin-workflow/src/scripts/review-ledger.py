#!/usr/bin/env python3
import sys
import os
import argparse
from datetime import datetime, timezone

# Add the parent directory of review_ledger to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from review_ledger.cli import (
    initialize_ledger,
    mutate_ledger,
    start_review,
    load_ledger,
    get_ledger_paths,
    render_review_markdown,
    build_acceptance_identity_payload,
)
from review_ledger.events import WorkflowIntegrityError
from review_ledger.projections import ReviewProjection
from review_ledger.git_adapter import create_source_checkpoint, push_review_ref, fetch_review_ref
from review_ledger.source_identity import compute_source_scope_hash
from review_ledger.bead_fsm import TERMINAL_FINDING_STATUSES

def parse_args():
    parser = argparse.ArgumentParser(description="Cross-Agent Review Ledger CLI tool.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    # Init
    p_init = subparsers.add_parser("init", help="Initialize a new ledger.")
    p_init.add_argument("--bead-id", required=True)
    p_init.add_argument("--repo-id", required=True)
    p_init.add_argument("--repo-path", default=".")
    p_init.add_argument("--include", dest="included_paths", action="append", default=[])
    p_init.add_argument("--exclude", dest="excluded_paths", action="append", default=[])
    p_init.add_argument("--generated", dest="generated_paths", action="append", default=[])
    p_init.add_argument("--nested-repository", dest="nested_paths", action="append", default=[])
    p_init.add_argument("--role", default="primary")
    p_init.add_argument("--review-ref", required=True)
    p_init.add_argument("--base-sha", default="HEAD")
    p_init.add_argument("--reviewed-sha", help=argparse.SUPPRESS)
    p_init.add_argument("--actor-role", default="worker")
    p_init.add_argument("--actor-id", required=True)

    # Checkpoint
    p_check = subparsers.add_parser("checkpoint", help="Create source checkpoint.")
    p_check.add_argument("--bead-id", required=True)
    p_check.add_argument("--repo-id", required=True)
    p_check.add_argument("--commit-msg", required=True)
    p_check.add_argument("--actor-role", default="worker")
    p_check.add_argument("--actor-id", required=True)
    p_check.add_argument("--lease-id")
    p_check.add_argument(
        "--workflow-id",
        help="Optional acceptance identity workflow ID (requires --attempt-id).",
    )
    p_check.add_argument(
        "--attempt-id",
        help="Optional acceptance identity attempt ID (requires --workflow-id).",
    )

    # Start Review
    p_start = subparsers.add_parser("start-review", help="Start the review phase.")
    p_start.add_argument("--bead-id", required=True)
    p_start.add_argument("--actor-role", default="reviewer")
    p_start.add_argument("--actor-id", required=True)
    p_start.add_argument("--lease-id")
    p_start.add_argument("--ttl-seconds", type=int, default=600)

    # Add Finding
    p_add = subparsers.add_parser("add-finding", help="Add a new review finding.")
    p_add.add_argument("--bead-id", required=True)
    p_add.add_argument("--finding-id", required=True)
    p_add.add_argument("--severity", choices=["CRITICAL", "IMPORTANT", "MINOR", "SUGGESTION"], required=True)
    p_add.add_argument("--actor-role", default="reviewer")
    p_add.add_argument("--actor-id", required=True)
    p_add.add_argument("--lease-id")

    # Fix Finding
    p_fix = subparsers.add_parser("fix-finding", help="Mark finding as fixed.")
    p_fix.add_argument("--bead-id", required=True)
    p_fix.add_argument("--finding-id", required=True)
    p_fix.add_argument("--actor-role", default="worker")
    p_fix.add_argument("--actor-id", required=True)
    p_fix.add_argument("--lease-id")

    # Dispute Finding
    p_disp = subparsers.add_parser("dispute-finding", help="Dispute a finding.")
    p_disp.add_argument("--bead-id", required=True)
    p_disp.add_argument("--finding-id", required=True)
    p_disp.add_argument("--reason", required=True)
    p_disp.add_argument("--actor-role", default="worker")
    p_disp.add_argument("--actor-id", required=True)
    p_disp.add_argument("--lease-id")

    # Request Clarification
    p_req_c = subparsers.add_parser("request-clarification", help="Request clarification for a disputed finding.")
    p_req_c.add_argument("--bead-id", required=True)
    p_req_c.add_argument("--finding-id", required=True)
    p_req_c.add_argument("--reason", required=True)
    p_req_c.add_argument("--actor-role", default="reviewer")
    p_req_c.add_argument("--actor-id", required=True)
    p_req_c.add_argument("--lease-id")

    # Provide Clarification
    p_prov_c = subparsers.add_parser("provide-clarification", help="Provide clarification.")
    p_prov_c.add_argument("--bead-id", required=True)
    p_prov_c.add_argument("--finding-id", required=True)
    p_prov_c.add_argument("--clarification", required=True)
    p_prov_c.add_argument("--actor-role", default="worker")
    p_prov_c.add_argument("--actor-id", required=True)
    p_prov_c.add_argument("--lease-id")

    # Propose Deferral
    p_prop_d = subparsers.add_parser("propose-deferral", help="Propose finding deferral.")
    p_prop_d.add_argument("--bead-id", required=True)
    p_prop_d.add_argument("--finding-id", required=True)
    p_prop_d.add_argument("--reason", required=True)
    p_prop_d.add_argument("--follow-up-bead-id", required=True)
    p_prop_d.add_argument("--follow-up-bead-title", required=True)
    p_prop_d.add_argument("--actor-role", default="worker")
    p_prop_d.add_argument("--actor-id", required=True)
    p_prop_d.add_argument("--lease-id")

    # Approve Deferral
    p_app_d = subparsers.add_parser("approve-deferral", help="Approve proposed deferral.")
    p_app_d.add_argument("--bead-id", required=True)
    p_app_d.add_argument("--finding-id", required=True)
    p_app_d.add_argument("--actor-role", default="reviewer")
    p_app_d.add_argument("--actor-id", required=True)
    p_app_d.add_argument("--lease-id")

    # Verify Finding
    p_ver = subparsers.add_parser("verify-finding", help="Verify finding fix.")
    p_ver.add_argument("--bead-id", required=True)
    p_ver.add_argument("--finding-id", required=True)
    p_ver.add_argument("--actor-role", default="reviewer")
    p_ver.add_argument("--actor-id", required=True)
    p_ver.add_argument("--lease-id")

    # Withdraw Finding
    p_withd = subparsers.add_parser("withdraw-finding", help="Withdraw finding.")
    p_withd.add_argument("--bead-id", required=True)
    p_withd.add_argument("--finding-id", required=True)
    p_withd.add_argument("--actor-role", default="reviewer")
    p_withd.add_argument("--actor-id", required=True)
    p_withd.add_argument("--lease-id")

    # Accept As Is
    p_acc = subparsers.add_parser("accept-as-is", help="Accept implementation as-is.")
    p_acc.add_argument("--bead-id", required=True)
    p_acc.add_argument("--finding-id", required=True)
    p_acc.add_argument("--actor-role", default="reviewer")
    p_acc.add_argument("--actor-id", required=True)
    p_acc.add_argument("--lease-id")

    # Approve Review
    p_app = subparsers.add_parser("approve", help="Approve the review state.")
    p_app.add_argument("--bead-id", required=True)
    p_app.add_argument("--actor-role", default="reviewer")
    p_app.add_argument("--actor-id", required=True)
    p_app.add_argument("--lease-id")
    p_app.add_argument(
        "--workflow-id",
        help="Optional acceptance identity workflow ID (requires --attempt-id).",
    )
    p_app.add_argument(
        "--attempt-id",
        help="Optional acceptance identity attempt ID (requires --workflow-id).",
    )

    # Reject / Invalidate
    p_rej = subparsers.add_parser("reject", help="Invalidate approval.")
    p_rej.add_argument("--bead-id", required=True)
    p_rej.add_argument("--reason", required=True)
    p_rej.add_argument("--actor-role", default="reviewer")
    p_rej.add_argument("--actor-id", required=True)
    p_rej.add_argument("--lease-id")

    # Record Human Decision
    p_hum_d = subparsers.add_parser("record-human-decision", help="Record a human decision.")
    p_hum_d.add_argument("--bead-id", required=True)
    p_hum_d.add_argument("--finding-id", required=True)
    p_hum_d.add_argument("--question", required=True)
    p_hum_d.add_argument("--decision", required=True)
    p_hum_d.add_argument("--reason", required=True)
    p_hum_d.add_argument("--actor-role", default="human")
    p_hum_d.add_argument("--actor-id", required=True)

    # Waive Finding
    p_waive = subparsers.add_parser("waive-finding", help="Waive a finding.")
    p_waive.add_argument("--bead-id", required=True)
    p_waive.add_argument("--finding-id", required=True)
    p_waive.add_argument("--reason", required=True)
    p_waive.add_argument("--actor-role", default="human")
    p_waive.add_argument("--actor-id", required=True)

    # Render
    p_render = subparsers.add_parser("render", help="Render review.md.")
    p_render.add_argument("--bead-id", required=True)
    p_render.add_argument("--check", action="store_true", help="Fail if output differs from disk.")

    # Validate
    p_val = subparsers.add_parser("validate", help="Validate ledger consistency.")
    p_val.add_argument("--bead-id", required=True)

    # Status
    p_stat = subparsers.add_parser("status", help="Get summary status.")
    p_stat.add_argument("--bead-id", required=True)

    # Transition Requested
    p_trans_req = subparsers.add_parser("transition-requested", help="Request a state transition.")
    p_trans_req.add_argument("--bead-id", required=True)
    p_trans_req.add_argument("--to", required=True)
    p_trans_req.add_argument("--actor-role", default="worker")
    p_trans_req.add_argument("--actor-id", required=True)
    p_trans_req.add_argument("--lease-id")

    return parser.parse_args()

def main():
    args = parse_args()
    
    try:
        if args.command == "init":
            scope = {
                "included_paths": args.included_paths,
                "excluded_artifact_paths": args.excluded_paths,
                "allowed_generated_paths": args.generated_paths,
                "nested_repository_paths": args.nested_paths,
            }
            checkpoint = initialize_ledger(
                bead_id=args.bead_id,
                repository_id=args.repo_id,
                role=args.role,
                repo_path=args.repo_path,
                review_ref=args.review_ref,
                base_ref=args.base_sha,
                scope=scope,
                actor_role=args.actor_role,
                actor_id=args.actor_id,
            )
            print(
                f"Initialized review ledger for bead {args.bead_id} "
                f"at {checkpoint.checkpoint_sha}"
            )

        elif args.command == "checkpoint":
            _, proj = load_ledger(args.bead_id)
            repository = next(
                (
                    item
                    for item in proj.repositories
                    if item["repository_id"] == args.repo_id
                ),
                None,
            )
            if repository is None:
                raise ValueError(f"Repository '{args.repo_id}' not found in ledger.")
            repository_path = os.path.abspath(
                os.path.join(os.getcwd(), repository.get("repository_path", "."))
            )
            checkpoint = create_source_checkpoint(
                repository_path,
                proj.source_scope,
                args.bead_id,
                base_ref=repository["review_base_sha"],
                review_ref=repository.get("checkpoint_ref")
                or repository.get("review_ref"),
                repository_id=args.repo_id,
                commit_msg=args.commit_msg,
            )
            repositories = [dict(item) for item in proj.repositories]
            for item in repositories:
                if item["repository_id"] == args.repo_id:
                    item.update(
                        {
                            "review_ref": checkpoint.checkpoint_ref,
                            "checkpoint_ref": checkpoint.checkpoint_ref,
                            "reviewed_source_sha": checkpoint.checkpoint_sha,
                            "checkpoint_sha": checkpoint.checkpoint_sha,
                            "source_scope_hash": checkpoint.source_scope_hash,
                            "source_tree_hash": checkpoint.source_tree_hash,
                            "reviewed_source_tree_hash": checkpoint.source_tree_hash,
                            "source_identity_status": "complete",
                        }
                    )
            payload = {"repositories": repositories}
            payload.update(
                build_acceptance_identity_payload(
                    task_id=args.bead_id,
                    workflow_id=args.workflow_id,
                    attempt_id=args.attempt_id,
                    repositories=repositories,
                )
            )
            mutate_ledger(
                args.bead_id,
                "source-checkpoint-created",
                payload,
                args.actor_role,
                args.actor_id,
                lease_id=args.lease_id,
            )
            print(f"Created source checkpoint: {checkpoint.checkpoint_sha}")

        elif args.command == "start-review":
            _, projection = start_review(
                args.bead_id,
                args.actor_id,
                requested_lease_id=args.lease_id,
                ttl_seconds=args.ttl_seconds,
                actor_role=args.actor_role,
            )
            print(f"Review phase started with lease {projection.active_lease.lease_id}.")

        elif args.command == "add-finding":
            payload = {"finding_id": args.finding_id, "severity": args.severity}
            mutate_ledger(
                args.bead_id, "finding-created", payload,
                args.actor_role, args.actor_id, lease_id=args.lease_id
            )
            print(f"Added finding {args.finding_id}")

        elif args.command == "fix-finding":
            payload = {"finding_id": args.finding_id}
            mutate_ledger(
                args.bead_id, "finding-fixed", payload,
                args.actor_role, args.actor_id, lease_id=args.lease_id
            )
            print(f"Marked finding {args.finding_id} as fixed")

        elif args.command == "dispute-finding":
            payload = {"finding_id": args.finding_id, "reason": args.reason}
            mutate_ledger(
                args.bead_id, "finding-disputed", payload,
                args.actor_role, args.actor_id, lease_id=args.lease_id
            )
            print(f"Disputed finding {args.finding_id}")

        elif args.command == "request-clarification":
            payload = {"finding_id": args.finding_id, "reason": args.reason}
            mutate_ledger(
                args.bead_id, "clarification-requested", payload,
                args.actor_role, args.actor_id, lease_id=args.lease_id
            )
            print(f"Requested clarification for finding {args.finding_id}")

        elif args.command == "provide-clarification":
            payload = {"finding_id": args.finding_id, "clarification": args.clarification}
            mutate_ledger(
                args.bead_id, "clarification-provided", payload,
                args.actor_role, args.actor_id, lease_id=args.lease_id
            )
            print(f"Provided clarification for finding {args.finding_id}")

        elif args.command == "propose-deferral":
            payload = {
                "finding_id": args.finding_id,
                "reason": args.reason,
                "follow_up_bead_id": args.follow_up_bead_id,
                "follow_up_bead_title": args.follow_up_bead_title
            }
            mutate_ledger(
                args.bead_id, "deferral-proposed", payload,
                args.actor_role, args.actor_id, lease_id=args.lease_id
            )
            print(f"Proposed deferral for finding {args.finding_id}")

        elif args.command == "approve-deferral":
            payload = {"finding_id": args.finding_id}
            mutate_ledger(
                args.bead_id, "deferral-approved", payload,
                args.actor_role, args.actor_id, lease_id=args.lease_id
            )
            print(f"Approved deferral for finding {args.finding_id}")

        elif args.command == "verify-finding":
            payload = {"finding_id": args.finding_id}
            mutate_ledger(
                args.bead_id, "finding-verified", payload,
                args.actor_role, args.actor_id, lease_id=args.lease_id
            )
            print(f"Verified finding {args.finding_id}")

        elif args.command == "withdraw-finding":
            payload = {"finding_id": args.finding_id}
            mutate_ledger(
                args.bead_id, "finding-withdrawn", payload,
                args.actor_role, args.actor_id, lease_id=args.lease_id
            )
            print(f"Withdrew finding {args.finding_id}")

        elif args.command == "accept-as-is":
            payload = {"finding_id": args.finding_id}
            mutate_ledger(
                args.bead_id, "finding-accepted-as-is", payload,
                args.actor_role, args.actor_id, lease_id=args.lease_id
            )
            print(f"Accepted finding {args.finding_id} as-is")

        elif args.command == "approve":
            # Gathers repository list and scope hash for approval snapshot
            log, proj = load_ledger(args.bead_id)
            scope_hash = compute_source_scope_hash(proj.source_scope)
            terminal_fids = [fid for fid, f in proj.findings.items() if f.status in TERMINAL_FINDING_STATUSES]
            
            payload = {
                "approved_repositories": proj.repositories,
                "source_scope_hash": scope_hash,
                "terminal_findings": terminal_fids
            }
            payload.update(
                build_acceptance_identity_payload(
                    task_id=args.bead_id,
                    workflow_id=args.workflow_id,
                    attempt_id=args.attempt_id,
                    repositories=proj.repositories,
                )
            )
            mutate_ledger(
                args.bead_id, "review-approved", payload,
                args.actor_role, args.actor_id, lease_id=args.lease_id
            )
            print("Review approved.")

        elif args.command == "reject":
            payload = {"reason": args.reason}
            mutate_ledger(
                args.bead_id, "review-approval-invalidated", payload,
                args.actor_role, args.actor_id, lease_id=args.lease_id
            )
            print("Review approval invalidated / rejected.")

        elif args.command == "record-human-decision":
            payload = {
                "finding_id": args.finding_id,
                "question": args.question,
                "decision": args.decision,
                "reason": args.reason
            }
            mutate_ledger(
                args.bead_id, "human-decision-recorded", payload,
                args.actor_role, args.actor_id, bypass_lease=True
            )
            print(f"Recorded human decision for finding {args.finding_id}")

        elif args.command == "waive-finding":
            payload = {"finding_id": args.finding_id, "reason": args.reason}
            mutate_ledger(
                args.bead_id, "finding-waived", payload,
                args.actor_role, args.actor_id, bypass_lease=True
            )
            print(f"Waived finding {args.finding_id}")

        elif args.command == "render":
            log, proj = load_ledger(args.bead_id)
            rendered = render_review_markdown(proj, log)
            _, md_path = get_ledger_paths(args.bead_id)
            
            if args.check:
                if not os.path.exists(md_path):
                    print("Error: review.md is missing from disk.", file=sys.stderr)
                    sys.exit(1)
                with open(md_path, "r", encoding="utf-8") as f:
                    disk_content = f.read()
                if disk_content != rendered:
                    print("Error: review.md on disk differs from rendered output.", file=sys.stderr)
                    sys.exit(1)
                print("review.md check passed.")
            else:
                with open(md_path, "w", encoding="utf-8") as f:
                    f.write(rendered)
                print(f"Rendered ledger to {md_path}")

        elif args.command == "validate":
            load_ledger(args.bead_id)
            print("Ledger validation passed successfully.")

        elif args.command == "transition-requested":
            payload = {"to": args.to}
            mutate_ledger(
                args.bead_id, args.to, payload,
                args.actor_role, args.actor_id, lease_id=args.lease_id
            )
            print(f"Transitioned bead {args.bead_id} to state {args.to}")

        elif args.command == "status":
            _, proj = load_ledger(args.bead_id)
            print(f"State: {proj.review_state}")
            print(f"Total Findings: {len(proj.findings)}")
            unresolved = [fid for fid, f in proj.findings.items() if f.status not in TERMINAL_FINDING_STATUSES]
            print(f"Unresolved Findings: {len(unresolved)} ({', '.join(unresolved)})")

    except WorkflowIntegrityError as e:
        print(f"Integrity Error: {e}", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)

if __name__ == "__main__":
    main()

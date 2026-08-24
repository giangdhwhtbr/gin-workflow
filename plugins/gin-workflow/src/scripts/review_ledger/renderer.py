from review_ledger.projections import ReviewProjection
from review_ledger.events import EventLog

def render_review_markdown(projection: ReviewProjection, event_log: EventLog) -> str:
    """
    Renders a deterministic Markdown representation of the review ledger
    conforming to spec §16.
    """
    lines = []
    lines.append("# Code Review Ledger")
    lines.append("")
    lines.append(f"**Bead Status:** `{projection.review_state}`")
    lines.append("")

    # Lease section
    lines.append("## Active Lease")
    if projection.active_lease:
        lease = projection.active_lease
        lines.append(f"- **Lease ID:** `{lease.lease_id}`")
        lines.append(f"- **Actor:** `{lease.actor_id}` ({lease.actor_role})")
        lines.append(f"- **Acquired:** `{lease.acquired_at}`")
        lines.append(f"- **Expires:** `{lease.expires_at}`")
        lines.append(f"- **Ledger Revision:** `{lease.current_ledger_revision}`")
    else:
        lines.append("*No active lease.*")
    lines.append("")

    # Approval section
    lines.append("## Review Approval")
    if projection.active_approval:
        app = projection.active_approval
        lines.append(f"- **Status:** Approved")
        lines.append(f"- **Approval Event ID:** `{app.event_id}`")
        lines.append(f"- **Source Scope Hash:** `{app.source_scope_hash}`")
        lines.append("- **Approved Repositories:**")
        for repo in sorted(app.approved_repositories, key=lambda x: x.get("repository_id", "")):
            r_sha = repo.get('reviewed_source_sha')
            r_tree = repo.get('reviewed_source_tree_hash')
            sha_str = r_sha[:7] if r_sha else "unknown"
            tree_str = r_tree[:7] if r_tree else "unknown"
            lines.append(f"  - `{repo.get('repository_id')}` (SHA: `{sha_str}`, Tree Hash: `{tree_str}`)")
    else:
        lines.append("*Not approved or approval has been invalidated.*")
    lines.append("")

    # Repositories section
    lines.append("## Tracked Repositories")
    if projection.repositories:
        for repo in sorted(projection.repositories, key=lambda x: x.get("repository_id", "")):
            lines.append(f"### Repository: `{repo.get('repository_id')}`")
            lines.append(f"- **Role:** `{repo.get('role')}`")
            lines.append(f"- **Review Ref:** `{repo.get('review_ref')}`")
            lines.append(f"- **Base SHA:** `{repo.get('review_base_sha')}`")
            lines.append(f"- **Reviewed SHA:** `{repo.get('reviewed_source_sha')}`")
            lines.append(f"- **Source Identity:** `{repo.get('source_identity_status', 'missing')}`")
            if repo.get("repository_path"):
                lines.append(f"- **Repository Path:** `{repo.get('repository_path')}`")
            if repo.get("checkpoint_ref"):
                lines.append(f"- **Checkpoint Ref:** `{repo.get('checkpoint_ref')}`")
            if repo.get("checkpoint_sha"):
                lines.append(f"- **Checkpoint SHA:** `{repo.get('checkpoint_sha')}`")
            if repo.get("source_scope_hash"):
                lines.append(f"- **Scope Hash:** `{repo.get('source_scope_hash')}`")
            tree_hash = repo.get("source_tree_hash") or repo.get("reviewed_source_tree_hash")
            if tree_hash:
                lines.append(f"- **Tree Hash:** `{tree_hash}`")
    else:
        lines.append("*No repositories registered.*")
    lines.append("")

    # Source Scope section
    lines.append("## Source Scope Configuration")
    if projection.source_scope:
        scope = projection.source_scope
        lines.append("- **Included Paths:**")
        for path in sorted(scope.get("included_paths", [])):
            lines.append(f"  - `{path}`")
        lines.append("- **Excluded Artifact Paths:**")
        for path in sorted(scope.get("excluded_artifact_paths", [])):
            lines.append(f"  - `{path}`")
        lines.append("- **Allowed Generated Paths:**")
        for path in sorted(scope.get("allowed_generated_paths", [])):
            lines.append(f"  - `{path}`")
    else:
        lines.append("*No source scope defined.*")
    lines.append("")

    # Findings summary table
    lines.append("## Findings Summary")
    if projection.findings:
        lines.append("| Finding ID | Severity | Status | Clarification Count | Linked Bead |")
        lines.append("| :--- | :--- | :--- | :---: | :--- |")
        for fid in sorted(projection.findings.keys()):
            f = projection.findings[fid]
            bead_link = f"`{f.follow_up_bead_id}`" if f.follow_up_bead_id else "-"
            lines.append(f"| `{fid}` | `{f.severity}` | `{f.status}` | {f.clarification_count} | {bead_link} |")
    else:
        lines.append("*No findings recorded.*")
    lines.append("")

    # Detailed findings section
    lines.append("## Findings Detail")
    if projection.findings:
        for fid in sorted(projection.findings.keys()):
            f = projection.findings[fid]
            lines.append(f"### `{fid}` ({f.severity})")
            lines.append(f"- **Status:** `{f.status}`")
            lines.append(f"- **Clarification Count:** {f.clarification_count}")
            if f.deferral_reason:
                lines.append(f"- **Deferral Reason:** {f.deferral_reason}")
            if f.follow_up_bead_id:
                lines.append(f"- **Follow-up Bead:** `{f.follow_up_bead_id}` (*{f.follow_up_bead_title}*)")
            if f.decision:
                lines.append(f"- **Human Decision:** {f.decision}")
            if f.waived_reason:
                lines.append(f"- **Waiver Reason:** {f.waived_reason}")
            lines.append("")
    else:
        lines.append("*No detailed findings.*")
    lines.append("")

    # Chronological history log
    lines.append("## Event Chronology")
    if event_log.events:
        lines.append("| Event ID | Timestamp | Action | Actor |")
        lines.append("| :--- | :--- | :--- | :--- |")
        for e in event_log.events:
            actor_str = f"`{e.actor.get('actor_id')}` ({e.actor.get('role')})"
            lines.append(f"| `{e.event_id}` | `{e.timestamp}` | `{e.action}` | {actor_str} |")
    else:
        lines.append("*No history events.*")
    lines.append("")

    return "\n".join(lines)

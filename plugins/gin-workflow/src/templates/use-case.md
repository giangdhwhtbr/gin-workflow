<!-- One use case of a capability: <specs>/<cap>/use-cases/<slug>.md. The slug (file name without .md) is its ID.
     Requirements: the REQ-IDs it covers, from the living spec or the open change's 02-spec-delta.md.
     Optional: Secondary actors, Trigger, Includes, Extends, every section but Main flow, and Actor when another
     use case includes this one; delete an unused line instead of leaving it empty.
     Actor: a role outside the system; a use case started on a schedule has the actor Scheduler, never System.
     Includes and Extends list slugs of other use cases of the same capability, comma-separated. The main flow
     step where an included use case runs says "Include <slug>". Extends names the use case this one extends;
     Trigger then gives the extension point and condition: "At step 3 of <slug>, when ...".
     Business rules cite REQ-IDs instead of restating them. Each alternative or exception flow ends with
     "Resume at step N" or "Use case ends".
     `gin specs lint` checks the title, Actor, Requirements, a numbered Main flow, and the slugs. -->
# <Use case name>

Actor: <primary actor>
Secondary actors: <actor>, <actor>
Trigger: <event that starts the use case>
Requirements: REQ-<CAP>-NNN
Includes: <slug>
Extends: <slug>

## Goal

## Preconditions

## Main flow
1. <actor action>
2. <system response>

## Alternative flows
### 2a. <condition>
1. <system response>
2. Resume at step 2.

## Exception flows
### 2e. <error or failure>
1. <system response>
2. Use case ends.

## Business rules

## Postconditions

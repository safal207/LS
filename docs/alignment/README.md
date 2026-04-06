# Alignment Stack

Current stack chain (sealed baseline):

`report -> guidance -> softening -> memory -> patterns -> recommendations -> feedback -> aggregation -> reputation -> adoption -> calibration`

## Next Arc

1. **Merge / cleanup / docs**
   - land open PRs in dependency order
   - close superseded PRs
   - keep this stack map as the reference contract

2. **Alignment Strategy Playbook MVP**
   - consolidate active strategy recommendations into one compact operational object:
     - `current_playbook_id`
     - `selected_strategy_ids`
     - `why_selected`
     - `confidence`
     - `risk_notes`

3. **Multi-Party Alignment State MVP**
   - add participant-aware alignment context:
     - `participant_id`
     - `participant_role`
     - `tension_axis`
     - `dominant_mismatch`
     - `support_need`
     - `current_alignment_posture`

4. **Collective Coordination / Bridge Graph MVP**
   - aggregate shared coordination view:
     - `shared_tension_map`
     - `mismatch_graph`
     - `bridge_candidates`
     - `stabilization_order`

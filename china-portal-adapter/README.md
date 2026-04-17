# China Portal Adapter

`china-portal-adapter` is a discovery-sidecar for Chinese job platforms.

It exists to complement:

- `career-ops-local`
- local role-pack scoring
- local tailored packet generation

It does not replace the main local-first job search stack.

See:

- `docs/runtime/china-portal-adapter-adoption-boundary.md`
- `docs/runtime/china-portal-adapter-capability-map.md`
- `docs/plans/2026-04-08-001-feat-china-portal-adapter-plan.md`

## Local-first Quick Start

Default local config:

- `D:\career-ops-local\config\china_portal_adapter.local.json`

Recommended first run:

1. run doctor first
   - `cmd /c china-portal-adapter\skills\china-portal-adapter\scripts\run_china_portal_doctor_from_config.cmd`
2. if Boss is ready but missing config, set the Boss list URL
   - `cmd /c china-portal-adapter\skills\china-portal-adapter\scripts\run_set_boss_live_scan_url.cmd --url "<boss-list-url>" --enable-live-scan`
3. run a bounded Boss live scan
   - `cmd /c china-portal-adapter\skills\china-portal-adapter\scripts\run_boss_live_scan_from_config.cmd`
4. run Boss scan -> shortlist -> tailor queue
   - `cmd /c china-portal-adapter\skills\china-portal-match-bridge\scripts\run_boss_shortlist_from_config.cmd`

Default output roots:

- `D:\career-ops-local\outputs\china-portal-adapter\doctor\`
- `D:\career-ops-local\outputs\china-portal-adapter\boss-live\`
- `D:\career-ops-local\outputs\china-portal-adapter\boss-shortlist\`

Hard boundary:

- list-page scan only
- normalize to `job_card`
- no greeting
- no auto-submit
- shortlist and tailor generation stay human-reviewed

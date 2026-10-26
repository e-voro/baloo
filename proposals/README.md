# Hot Standby Feedback proposal status

`hsf-xid64-distinct-tag.patch` is the minimal proposal Evgeny approved on
2026-10-26. It is retained for the review history, not as an additional patch
to apply to the current tree.

The implemented changes and tests are recorded in commits `d99f3a1486c` and
`331942f4995`; public documentation is in `5d5fbdf0901`. Use the corresponding
`pg19-hsf-xid64-tag.patch`, `pg19-hsf-future-horizons.patch` and
`pg19-conversion-feedback-docs.patch` entries in the active series.

The implementation additionally rejects the old tag explicitly, validates the
payload end and ignores future full-XID horizons. Both peers must support H;
this intentionally rejects earlier xid64 feedback peers still sending h.

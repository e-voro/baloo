/* Focused smoke coverage for the xid64 64-bit GUC/reloption infrastructure. */
#include "postgres.h"
#include "fmgr.h"
#include "access/reloptions.h"
#include "utils/builtins.h"
#include "utils/guc.h"

PG_MODULE_MAGIC;

void _PG_init(void);
PG_FUNCTION_INFO_V1(xid64_parse);
PG_FUNCTION_INFO_V1(xid64_serialize);
PG_FUNCTION_INFO_V1(xid64_reloption);

static int64 probe_value;
static int64 probe_ms;
static relopt_kind probe_kind;

typedef struct ProbeOptions
{
	int32 vl_len_;
	int64 value;
} ProbeOptions;

void
_PG_init(void)
{
	DefineCustomInt64Variable("xid64_probe.value", "64-bit test value", NULL,
		&probe_value, 0, PG_INT64_MIN, PG_INT64_MAX, PGC_USERSET, 0,
		NULL, NULL, NULL);
	DefineCustomInt64Variable("xid64_probe.ms", "64-bit unit test value", NULL,
		&probe_ms, 0, PG_INT64_MIN, PG_INT64_MAX, PGC_USERSET, GUC_UNIT_MS,
		NULL, NULL, NULL);
	probe_kind = add_reloption_kind();
	add_int64_reloption(probe_kind, "probe_value", "64-bit reloption test",
		0, PG_INT64_MIN, PG_INT64_MAX, AccessExclusiveLock);
}

Datum
xid64_parse(PG_FUNCTION_ARGS)
{
	char *input = text_to_cstring(PG_GETARG_TEXT_PP(0));
	int64 value;
	const char *hint = NULL;
	bool ok = parse_int64(input, &value,
		PG_GETARG_BOOL(1) ? GUC_UNIT_MS : 0,
		PG_GETARG_BOOL(2) ? &hint : NULL);

	if (!ok)
		PG_RETURN_NULL();
	PG_RETURN_INT64(value);
}

Datum
xid64_reloption(PG_FUNCTION_ARGS)
{
	static const relopt_parse_elt elements[] = {
		{"probe_value", RELOPT_TYPE_INT64, offsetof(ProbeOptions, value)}
	};
	ProbeOptions *opts = build_reloptions(PG_GETARG_DATUM(0), true, probe_kind,
		sizeof(ProbeOptions), elements, lengthof(elements));
	int64 value = opts ? opts->value : 0;

	if (opts)
		pfree(opts);
	PG_RETURN_INT64(value);
}

Datum
xid64_serialize(PG_FUNCTION_ARGS)
{
	Size size = EstimateGUCStateSpace();
	char *state = palloc(size);

	SerializeGUCState(size, state);
	pfree(state);
	PG_RETURN_BOOL(true);
}

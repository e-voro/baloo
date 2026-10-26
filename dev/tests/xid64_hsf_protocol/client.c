/* Exercise the real physical-replication CopyData dispatcher via libpq. */
#include <libpq-fe.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>

static void
put64(char *buf, uint64_t value)
{
	for (int i = 7; i >= 0; --i)
	{
		buf[i] = value & 0xff;
		value >>= 8;
	}
}

int
main(int argc, char **argv)
{
	char conninfo[4096];
	char sql[512];
	char payload[26] = {0};
	char lsn[64];
	PGconn *stream;
	PGconn *observer;
	PGresult *res;
	int pid;
	int stable = 0;
	uint64_t xmin;

	if (argc != 4)
		return 1;
	xmin = strtoull(argv[3], NULL, 10);
	snprintf(conninfo, sizeof(conninfo), "%s replication=true application_name=xid64_hsf_probe", argv[1]);
	stream = PQconnectdb(conninfo);
	observer = PQconnectdb(argv[1]);
	if (PQstatus(stream) != CONNECTION_OK || PQstatus(observer) != CONNECTION_OK)
	{
		fprintf(stderr, "connection setup failed: %s", PQerrorMessage(stream));
		return 1;
	}
	pid = PQbackendPID(stream);
	res = PQexec(stream, "IDENTIFY_SYSTEM");
	if (PQresultStatus(res) != PGRES_TUPLES_OK || PQntuples(res) != 1)
		return 1;
	snprintf(lsn, sizeof(lsn), "%s", PQgetvalue(res, 0, 2));
	PQclear(res);
	snprintf(sql, sizeof(sql), "START_REPLICATION PHYSICAL %s", lsn);
	res = PQexec(stream, sql);
	if (PQresultStatus(res) != PGRES_COPY_BOTH)
	{
		fprintf(stderr, "START_REPLICATION failed: %s", PQerrorMessage(stream));
		return 1;
	}
	PQclear(res);
	payload[0] = argv[2][0];
	put64(payload + 1, 1); /* nonzero reply timestamp proves message processing */
	put64(payload + 9, payload[0] == 'h' ? (UINT64_C(100) << 32) | 1 : xmin);
	if (strcmp(argv[2], "Hcatalog") == 0)
	{
		put64(payload + 9, 0);
		put64(payload + 17, xmin);
	}
	if (PQputCopyData(stream, payload, strcmp(argv[2], "H+") == 0 ? 26 : 25) != 1 ||
		PQflush(stream) != 0)
		return 1;
	PQsetnonblocking(stream, 1);
	for (int attempt = 0; attempt < 300; ++attempt)
	{
		char *data = NULL;
		int nread;

		if (!PQconsumeInput(stream))
			goto rejected;
		while ((nread = PQgetCopyData(stream, &data, 1)) > 0)
			PQfreemem(data);
		if (nread < 0)
			goto rejected;
		if (payload[0] == 'H' && strcmp(argv[2], "H+") != 0)
		{
			int ignored = strcmp(argv[2], "Hfuture") == 0 ||
				strcmp(argv[2], "Hcatalog") == 0;

			snprintf(sql, sizeof(sql),
					 "SELECT backend_xmin::text, reply_time IS NOT NULL FROM pg_stat_replication WHERE pid=%d", pid);
			res = PQexec(observer, sql);
			if (PQresultStatus(res) == PGRES_TUPLES_OK && PQntuples(res) == 1 &&
				((!ignored && strcmp(PQgetvalue(res, 0, 0), argv[3]) == 0) ||
				 (ignored && PQgetisnull(res, 0, 0) &&
				  strcmp(PQgetvalue(res, 0, 1), "t") == 0)))
			{
				/* Do not mistake the brief reply-time/xmin publication window
				 * for a rejected horizon: require stable observations. */
				if (ignored && ++stable < 10)
				{
					PQclear(res);
					usleep(10000);
					continue;
				}
				puts(ignored ? "future feedback ignored" : "full-XID feedback accepted");
				PQclear(res);
				PQfinish(observer);
				PQfinish(stream);
				return 0;
			}
			stable = 0;
			PQclear(res);
		}
		usleep(10000);
	}
	fprintf(stderr, "feedback test timed out\n");
	return 1;

rejected:
	fprintf(stderr, "server closed feedback connection\n");
	PQfinish(observer);
	PQfinish(stream);
	return 2;
}

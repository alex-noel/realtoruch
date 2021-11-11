# Search convergence on the controlled reference profile

On **2026-11-11 at 22:38:55–22:39:21 UTC**, the integrator ran the existing
`test_hundred_changed_homes_converge` on clean commit
`a30d1d56f672f277925543fb0ed6b181596cc57f`. All 100 committed changed homes reached
their expected searchable revisions and 4,200 PLN price in **0.431287 seconds**.
The target is 30 seconds. Pytest reported **1 passed, 0 failed, 0 skipped**.
This closes T08-AC07 / T08-TC07 for the controlled local profile below.

The earlier 0.325006-second result used an unrestricted six-CPU Docker VM and
did not establish this gate. It remains historical evidence only.

## Resource profile

All application test code, SQL and Elasticsearch ran inside three disposable
containers. The host only orchestrated startup, readiness checks and cleanup.
CPU sets were disjoint, and Docker inspection verified the limits after the
test. Memory plus swap equalled each memory limit, allowing no additional swap.

| Component | CPU set | CPU quota | Memory limit | Runtime |
| --- | --- | ---: | ---: | --- |
| Python test/indexer driver | 0 | 1 CPU | 2 GiB | Python 3.12.16 base image, arm64; pytest 8.4.2 |
| PostgreSQL | 1 | 1 CPU | 2 GiB | 16.15 Alpine, x86_64 under local emulation |
| Elasticsearch | 2,3 | 2 CPUs | 4 GiB | 8.19.6, native arm64; 1 GiB fixed JVM heap |
| **Total** | **0–3** | **4 CPUs** | **8 GiB** | No container was OOM-killed |

This is a four-CPU/eight-GiB **container resource budget**, not a claim that the
physical machine or Docker VM had only those resources. Host: Apple M4 Pro,
64 GiB, macOS 15.7.7 arm64; Docker VM: six CPUs and approximately 15 GiB. No
global Docker settings were changed. Default container security protections
remained enabled. No competing sustained benchmark was running.

The immutable local image IDs were:

- Driver: `sha256:8ae7f21392303e20384c9eb3762f746dc817ac5c0fd4612d49050923b325994f`.
- PostgreSQL: `sha256:aa6cb33cf4c19c765cefcf48d96176258800870a9a1e930ad126200f9d825139`.
- Elasticsearch: `sha256:bfb2108076735fbfc5dcd5d49f12f5aa93fab9759034c55f7da3b4345606c903`.

## Workload and reproduction

The unchanged service test creates 100 distinct synthetic homes, commits 100
price changes and their search revisions in one transaction, then starts the
timer. It invokes one indexer immediately, explicitly refreshes Elasticsearch
after each pass, and checks every returned ID, revision and price. The fallback
poll interval is 0.2 seconds. There was no warm-up and one measured batch. This
does not measure the normal worker's five-second polling delay, provider
collection latency, sustained throughput or deployed availability.

To repeat the same profile on a host with at least four available Docker CPUs:

1. Use a clean checkout and disposable run directory. Build or use a runtime
   image from `backend/Dockerfile`, record its immutable ID and Python version,
   and provide the locked pytest dependencies. The recorded run copied the
   installed pure-Python pytest 8.4.2, iniconfig 2.3.1, pluggy 1.7.0, Pygments
   2.21.0 and packaging 26.3 files into a read-only test-dependency mount. Plugin
   auto-loading was disabled.
2. Create a uniquely named internal Docker network and three uniquely named
   containers, all with an unpredictable ownership label. Use explicit image
   platforms; do not inherit `DOCKER_DEFAULT_PLATFORM`. Use `--cpus 1
   --cpuset-cpus 0 --memory 2g --memory-swap 2g` for the driver, the same limits
   with CPU set `1` for PostgreSQL, and `--cpus 2 --cpuset-cpus 2,3 --memory 4g
   --memory-swap 4g` for Elasticsearch. No public ports are needed.
3. Run PostgreSQL with a synthetic database/user/password and Elasticsearch
   with single-node discovery and security disabled on this isolated network.
   Set `ES_JAVA_OPTS=-Xms1g -Xmx1g`. Wait for both services to report ready.
4. Mount `backend` and `infra/sql` read-only into the driver, plus an empty
   writable artifact directory. Set `PYTHONPATH` to the mounted backend,
   backend tests and test dependencies; set `REALTORUCH_SQL_DIR` to the mounted
   SQL directory. Set `TEST_POSTGRES_URL` and `TEST_ELASTICSEARCH_URL` to the
   owned services, a unique `VERIFY_RUN_ID`, `TMPDIR` to the artifact directory,
   `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1`, file-only email and disabled push. Do not
   mount a developer environment file or real catalog.
5. Execute the following command **inside the limited driver**, using its
   mounted test path:

   ```sh
   python -m pytest /repo/backend/tests/test_service_integration.py::test_hundred_changed_homes_converge -q -s -p no:cacheprovider --junitxml=/work/results.xml
   ```

6. Retain `t08-convergence.json`, the test result, actual UTC times, revision and
   inspected CPU/memory/image metadata. Require one passing test without a
   skip. Remove only containers and network whose ownership label matches the
   run, even if the test fails.

The exact local invocation was
`.venv/bin/python .local/verification/T08/reference-profile/run.py`.
The run-owned report, full command arguments, driver log and XML are retained
in ignored `.local/verification/T08/reference-profile/t08-reference-858c9650/`.
Cleanup removed all three containers and their network. No cloud resources,
external delivery, deployment or push were involved.

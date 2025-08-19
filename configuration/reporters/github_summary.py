from configuration.workers.worker import WorkerPool

SUMMARY_FILE_NAME = "checkconfig_summary.md"


def workers_load(worker_pool: WorkerPool) -> None:
    """
    Shows allocated and total jobs (CPU's) for each worker in the pool.
    Then a detail is shown with each builder and the jobs it has requested from
    the worker.
    The output is written in markdown format to SUMMARY_FILE_NAME.
    """
    with open(SUMMARY_FILE_NAME, "a") as f:
        f.write(f"## Worker load status\n")
        for arch in worker_pool.workers:

            f.write(f"### Arch: {arch}\n")
            f.write("| Worker | Total Jobs | Requested Jobs |\n")
            f.write("|-------------|------------|----------------|\n")
            for worker in worker_pool.workers[arch]:
                requested_jobs = worker.requested_jobs
                total_jobs = worker.total_jobs

                # Add warning if requested_jobs exceeds total_jobs
                warning = "⚠️ " if requested_jobs > total_jobs else ""

                f.write(
                    f"| {worker.name} | {total_jobs} | {warning}{requested_jobs} |\n"
                )

            f.write("\n### Builders Assigned\n")
            f.write("| Worker | Builder | Requested Jobs |\n")
            f.write("|-------------|---------|----------------|\n")
            for worker in worker_pool.workers[arch]:
                if worker.builders:
                    for builder_name, requested_jobs in worker.builders.items():
                        f.write(
                            f"| {worker.name} | {builder_name} | {requested_jobs} |\n"
                        )
                else:
                    f.write(f"| {worker.name} | None | None |\n")

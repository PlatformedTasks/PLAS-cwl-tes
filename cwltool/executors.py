# -*- coding: utf-8 -*-
""" Single and multi-threaded executors."""
import datetime
import os
import tempfile
import threading
import logging
from threading import Lock
from abc import ABCMeta, abstractmethod
from typing import Any, Dict, Iterable, List, Optional, Set, Tuple, Union

import psutil
from six import string_types, with_metaclass
from typing_extensions import Text  # pylint: disable=unused-import
from future.utils import raise_from
from schema_salad.validate import ValidationException

from .builder import Builder  # pylint: disable=unused-import
from .context import (RuntimeContext,  # pylint: disable=unused-import
                      getdefault)
from .errors import WorkflowException
from .job import JobBase  # pylint: disable=unused-import
from .loghandler import _logger
from .mutation import MutationManager
from .process import Process  # pylint: disable=unused-import
from .process import cleanIntermediate, relocateOutputs
from .provenance import ProvenanceProfile
from .utils import DEFAULT_TMP_PREFIX
from .workflow import Workflow, WorkflowJob, WorkflowJobStep
from .command_line_tool import CallbackJob

TMPDIR_LOCK = Lock()


class JobExecutor(with_metaclass(ABCMeta, object)):
    """Abstract base job executor."""

    def __init__(self):
        # type: (...) -> None
        """Initialize."""
        self.final_output = []  # type: List[Union[Dict[Text, Any], List[Dict[Text, Any]]]]
        self.final_status = []  # type: List[Text]
        self.output_dirs = set()  # type: Set[Text]

    def __call__(self, *args, **kwargs):  # type: (*Any, **Any) -> Any
        return self.execute(*args, **kwargs)

    def output_callback(self, out, process_status):  # type: (Dict[Text, Any], Text) -> None
        """Collect the final status and outputs."""
        self.final_status.append(process_status)
        self.final_output.append(out)

    @abstractmethod
    def run_jobs(self,
                 process,           # type: Process
                 job_order_object,  # type: Dict[Text, Any]
                 logger,            # type: logging.Logger
                 runtime_context     # type: RuntimeContext
                ):  # type: (...) -> None
        """Execute the jobs for the given Process."""

    def execute(self,
                process,           # type: Process
                job_order_object,  # type: Dict[Text, Any]
                runtime_context,   # type: RuntimeContext
                logger=_logger,    # type: logging.Logger
               ):  # type: (...) -> Tuple[Optional[Union[Dict[Text, Any], List[Dict[Text, Any]]]], Text]
        """Execute the process."""
        if not runtime_context.basedir:
            raise WorkflowException("Must provide 'basedir' in runtimeContext")

        finaloutdir = None  # Type: Optional[Text]
        original_outdir = runtime_context.outdir
        if isinstance(original_outdir, string_types):
            finaloutdir = os.path.abspath(original_outdir)
        runtime_context = runtime_context.copy()
        outdir = tempfile.mkdtemp(
            prefix=getdefault(runtime_context.tmp_outdir_prefix, DEFAULT_TMP_PREFIX))
        self.output_dirs.add(outdir)
        runtime_context.outdir = outdir
        runtime_context.mutation_manager = MutationManager()
        runtime_context.toplevel = True
        runtime_context.workflow_eval_lock = threading.Condition(threading.RLock())

        job_reqs = None
        if "https://w3id.org/cwl/cwl#requirements" in job_order_object:
            if process.metadata.get("http://commonwl.org/cwltool#original_cwlVersion") == 'v1.0':
                raise WorkflowException(
                    "`cwl:requirements` in the input object is not part of CWL "
                    "v1.0. You can adjust to use `cwltool:overrides` instead; or you "
                    "can set the cwlVersion to v1.1")
            job_reqs = job_order_object["https://w3id.org/cwl/cwl#requirements"]
        elif ("cwl:defaults" in process.metadata
              and "https://w3id.org/cwl/cwl#requirements"
              in process.metadata["cwl:defaults"]):
            if process.metadata.get("http://commonwl.org/cwltool#original_cwlVersion") == 'v1.0':
                raise WorkflowException(
                    "`cwl:requirements` in the input object is not part of CWL "
                    "v1.0. You can adjust to use `cwltool:overrides` instead; or you "
                    "can set the cwlVersion to v1.1")
            job_reqs = process.metadata["cwl:defaults"]["https://w3id.org/cwl/cwl#requirements"]
        if job_reqs is not None:
            for req in job_reqs:
                process.requirements.append(req)

        self.run_jobs(process, job_order_object, logger, runtime_context)

        if self.final_output and self.final_output[0] is not None and finaloutdir is not None:
            self.final_output[0] = relocateOutputs(
                self.final_output[0], finaloutdir, self.output_dirs,
                runtime_context.move_outputs, runtime_context.make_fs_access(""),
                getdefault(runtime_context.compute_checksum, True),
                path_mapper=runtime_context.path_mapper)

        if runtime_context.rm_tmpdir:
            if runtime_context.cachedir is None:
                output_dirs = self.output_dirs  # type: Iterable[Any]
            else:
                output_dirs = filter(lambda x: not x.startswith(
                    runtime_context.cachedir), self.output_dirs)
            cleanIntermediate(output_dirs)

        if self.final_output and self.final_status:

            if runtime_context.research_obj is not None and \
                    isinstance(process, (JobBase, Process, WorkflowJobStep,
                                         WorkflowJob)) and process.parent_wf:
                process_run_id = None
                name = "primary"
                process.parent_wf.generate_output_prov(self.final_output[0],
                                                       process_run_id, name)
                process.parent_wf.document.wasEndedBy(
                    process.parent_wf.workflow_run_uri, None, process.parent_wf.engine_uuid,
                    datetime.datetime.now())
                process.parent_wf.finalize_prov_profile(name=None)
            return (self.final_output[0], self.final_status[0])
        return (None, "permanentFail")


class SingleJobExecutor(JobExecutor):
    """Default single-threaded CWL reference executor."""

    def run_jobs(self,
                 process,           # type: Process
                 job_order_object,  # type: Dict[Text, Any]
                 logger,            # type: logging.Logger
                 runtime_context    # type: RuntimeContext
                ):  # type: (...) -> None

        process_run_id = None  # type: Optional[str]

        # define provenance profile for single commandline tool
        if not isinstance(process, Workflow) \
                and runtime_context.research_obj is not None:
            process.provenance_object = ProvenanceProfile(
                runtime_context.research_obj,
                full_name=runtime_context.cwl_full_name,
                host_provenance=False,
                user_provenance=False,
                orcid=runtime_context.orcid,
                # single tool execution, so RO UUID = wf UUID = tool UUID
                run_uuid=runtime_context.research_obj.ro_uuid,
                fsaccess=runtime_context.make_fs_access(''))
            process.parent_wf = process.provenance_object
        jobiter = process.job(job_order_object, self.output_callback,
                              runtime_context)

        try:
            for job in jobiter:
                if job is not None:
                    if runtime_context.builder is not None:
                        job.builder = runtime_context.builder
                    if job.outdir is not None:
                        self.output_dirs.add(job.outdir)
                    if runtime_context.research_obj is not None:
                        if not isinstance(process, Workflow):
                            prov_obj = process.provenance_object
                        else:
                            prov_obj = job.prov_obj
                        if prov_obj:
                            runtime_context.prov_obj = prov_obj
                            prov_obj.fsaccess = runtime_context.make_fs_access('')
                            prov_obj.evaluate(
                                process, job, job_order_object,
                                runtime_context.research_obj)
                            process_run_id =\
                                prov_obj.record_process_start(process, job)
                            runtime_context = runtime_context.copy()
                        runtime_context.process_run_id = process_run_id
                    job.run(runtime_context)
                else:
                    logger.error("Workflow cannot make any more progress.")
                    break
        except (ValidationException, WorkflowException):  # pylint: disable=try-except-raise
            raise
        except Exception as err:
            logger.exception("Got workflow error")
            raise_from(WorkflowException(Text(err)), err)


class MultithreadedJobExecutor(JobExecutor):
    """
    Experimental multi-threaded CWL executor.

    Does simple resource accounting, will not start a job unless it
    has cores / ram available, but does not make any attempt to
    optimize usage.
    """

    def __init__(self):  # type: () -> None
        """Initialize."""
        super(MultithreadedJobExecutor, self).__init__()
        self.threads = set()  # type: Set[threading.Thread]
        self.exceptions = []  # type: List[WorkflowException]
        self.pending_jobs = []  # type: List[Union[JobBase, WorkflowJob]]
        self.pending_jobs_lock = threading.Lock()

        self.max_ram = int(psutil.virtual_memory().available / 2**20)
        self.max_cores = psutil.cpu_count()
        self.allocated_ram = 0
        self.allocated_cores = 0

    def select_resources(self, request, runtime_context):  # pylint: disable=unused-argument
        # type: (Dict[str, int], RuntimeContext) -> Dict[str, int]
        """Naïve check for available cpu cores and memory."""
        result = {}  # type: Dict[str, int]
        maxrsc = {
            "cores": self.max_cores,
            "ram": self.max_ram
        }
        for rsc in ("cores", "ram"):
            if request[rsc+"Min"] > maxrsc[rsc]:
                raise WorkflowException(
                    "Requested at least %d %s but only %d available" %
                    (request[rsc+"Min"], rsc, maxrsc[rsc]))
            if request[rsc+"Max"] < maxrsc[rsc]:
                result[rsc] = request[rsc+"Max"]
            else:
                result[rsc] = maxrsc[rsc]

        return result

    def _runner(self, job, runtime_context, TMPDIR_LOCK):
        # type: (Union[JobBase, WorkflowJob, CallbackJob], RuntimeContext, threading.Lock) -> None
        """Job running thread."""

        try:
            _logger.debug("job: {}, runtime_context: {}, TMPDIR_LOCK: {}".format(job, runtime_context, TMPDIR_LOCK))
            job.run(runtime_context, TMPDIR_LOCK)
        except WorkflowException as err:
            _logger.exception("Got workflow error")
            self.exceptions.append(err)
        except Exception as err:  # pylint: disable=broad-except
            _logger.exception("Got workflow error")
            self.exceptions.append(WorkflowException(Text(err)))
        finally:
            if runtime_context.workflow_eval_lock:
                with runtime_context.workflow_eval_lock:
                    self.threads.remove(threading.current_thread())
                    if isinstance(job, JobBase):
                        self.allocated_ram -= job.builder.resources["ram"]
                        self.allocated_cores -= job.builder.resources["cores"]
                    runtime_context.workflow_eval_lock.notifyAll()

    def run_job(self,
                job,             # type: Union[JobBase, WorkflowJob, None]
                runtime_context  # type: RuntimeContext
               ):  # type: (...) -> None
        """Execute a single Job in a seperate thread."""
        if job is not None:
            with self.pending_jobs_lock:
                self.pending_jobs.append(job)
        with self.pending_jobs_lock:
            n = 0
            while (n+1) <= len(self.pending_jobs):
                job = self.pending_jobs[n]
                if isinstance(job, JobBase):
                    if ((job.builder.resources["ram"])
                        > self.max_ram
                        or (job.builder.resources["cores"])
                        > self.max_cores):
                        _logger.error(
                            'Job "%s" cannot be run, requests more resources (%s) '
                            'than available on this host (max ram %d, max cores %d',
                            job.name, job.builder.resources,
                            self.allocated_ram,
                            self.allocated_cores,
                            self.max_ram,
                            self.max_cores)
                        self.pending_jobs.remove(job)
                        return

                    if ((self.allocated_ram + job.builder.resources["ram"])
                        > self.max_ram
                        or (self.allocated_cores + job.builder.resources["cores"])
                        > self.max_cores):
                        _logger.debug(
                            'Job "%s" cannot run yet, resources (%s) are not '
                            'available (already allocated ram is %d, allocated cores is %d, '
                            'max ram %d, max cores %d',
                            job.name, job.builder.resources,
                            self.allocated_ram,
                            self.allocated_cores,
                            self.max_ram,
                            self.max_cores)
                        n += 1
                        continue

                thread = threading.Thread(target=self._runner, args=(job, runtime_context, TMPDIR_LOCK))
                thread.daemon = True
                self.threads.add(thread)
                if isinstance(job, JobBase):
                    self.allocated_ram += job.builder.resources["ram"]
                    self.allocated_cores += job.builder.resources["cores"]
                thread.start()
                self.pending_jobs.remove(job)

    def wait_for_next_completion(self, runtime_context):
        # type: (RuntimeContext) -> None
        """Wait for jobs to finish."""
        if runtime_context.workflow_eval_lock is not None:
            runtime_context.workflow_eval_lock.wait()
        if self.exceptions:
            raise self.exceptions[0]

    def run_jobs(self,
                 process,           # type: Process
                 job_order_object,  # type: Dict[Text, Any]
                 logger,            # type: logging.Logger
                 runtime_context    # type: RuntimeContext
                ):  # type: (...) -> None


        jobiter = process.job(job_order_object, self.output_callback,
                              runtime_context)

        if runtime_context.workflow_eval_lock is None:
            raise WorkflowException(
                "runtimeContext.workflow_eval_lock must not be None")

        runtime_context.workflow_eval_lock.acquire()

        for job in jobiter:
            if job is not None:
                if isinstance(job, JobBase):
                    job.builder = runtime_context.builder or job.builder
                    if job.outdir is not None:
                        self.output_dirs.add(job.outdir)

            self.run_job(job, runtime_context)

            if job is None:
                if self.threads:
                    self.wait_for_next_completion(runtime_context)
                else:
                    logger.error("Workflow cannot make any more progress.")
                    break

        self.run_job(None, runtime_context)
        while self.threads:
            self.wait_for_next_completion(runtime_context)
            self.run_job(None, runtime_context)

        runtime_context.workflow_eval_lock.release()

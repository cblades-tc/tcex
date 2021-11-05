"""TcEx Framework"""

# standard library
import inspect
import logging
import os
import platform
import signal
import threading
from typing import Optional, Union

# third-party
from redis import Redis
from requests import Session

# first-party
from tcex.api.tc.v2.metrics import Metrics
from tcex.api.tc.v2.notifications import Notifications
from tcex.api.tc.v3.v3 import V3
from tcex.app_config.install_json import InstallJson
from tcex.app_feature import AdvancedRequest
from tcex.backports import cached_property
from tcex.batch.batch import Batch
from tcex.batch.batch_submit import BatchSubmit
from tcex.batch.batch_writer import BatchWriter
from tcex.datastore import Cache, DataStore
from tcex.exit.exit import ExitCode, ExitService
from tcex.input.input import Input
from tcex.key_value_store import KeyValueApi, KeyValueRedis, RedisClient
from tcex.logger.logger import Logger  # pylint: disable=no-name-in-module
from tcex.logger.trace_logger import TraceLogger  # pylint: disable=no-name-in-module
from tcex.playbook import Playbook
from tcex.pleb.proxies import proxies
from tcex.pleb.registry import registry
from tcex.pleb.scoped_property import scoped_property
from tcex.services.api_service import ApiService
from tcex.services.common_service_trigger import CommonServiceTrigger
from tcex.services.webhook_trigger_service import WebhookTriggerService
from tcex.sessions import ExternalSession, TcSession
from tcex.tokens import Tokens
from tcex.utils import Utils


class TcEx:
    """Provides basic functionality for all types of TxEx Apps.

    Args:
        config (dict, kwargs): A dictionary containing configuration items typically used by
            external Apps.
        config_file (str, kwargs): A filename containing JSON configuration items typically used
            by external Apps.
    """

    def __init__(self, **kwargs):
        """Initialize Class Properties."""
        # catch interupt signals specifically based on thread name
        signal.signal(signal.SIGINT, self._signal_handler)
        if platform.system() != 'Windows':
            signal.signal(signal.SIGHUP, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)

        # Property defaults
        self._config: dict = kwargs.get('config') or {}
        self._log = None
        self._jobs = None
        self._redis_client = None
        self._service = None
        self.ij = InstallJson()
        self.main_os_pid = os.getpid()

        # init inputs
        self.inputs = Input(self._config, kwargs.get('config_file'))

        # add methods to registry
        registry.register(self)
        registry.add_method(self.exit)

        # log standard App info early so it shows at the top of the logfile
        self.logger.log_info(self.inputs.data_unresolved)

    def _signal_handler(self, signal_interrupt: int, _) -> None:
        """Handle signal interrupt."""
        call_file: str = os.path.basename(inspect.stack()[1][0].f_code.co_filename)
        call_module: str = inspect.stack()[1][0].f_globals['__name__'].lstrip('Functions.')
        call_line: int = inspect.stack()[1][0].f_lineno
        self.log.error(
            f'App interrupted - file: {call_file}, method: {call_module}, line: {call_line}.'
        )
        exit_code = ExitCode.SUCCESS
        if threading.current_thread().name == 'MainThread' and signal_interrupt in (2, 15):
            exit_code = ExitCode.FAILURE

        self.exit(exit_code, 'The App received an interrupt signal and will now exit.')

    @property
    def _user_agent(self):
        """Return a User-Agent string."""
        return {
            'User-Agent': (
                f'TcEx/{__import__(__name__).__version__}, '
                f'{self.ij.data.display_name}/{self.ij.data.program_version}'
            )
        }

    def advanced_request(
        self, session: Session, timeout: Optional[int] = 600, output_prefix: Optional[str] = None
    ) -> AdvancedRequest:
        """Return instance of AdvancedRequest.

        Args:
            session: An instance of requests.Session.
            timeout: The number of second before timing out the request.
            output_prefix: A value to prepend to outputs.
        """
        return AdvancedRequest(self.inputs, self.playbook, session, timeout, output_prefix)

    def batch(
        self,
        owner: str,
        action: Optional[str] = 'Create',
        attribute_write_type: Optional[str] = 'Replace',
        halt_on_error: Optional[bool] = False,
        playbook_triggers_enabled: Optional[bool] = False,
        tag_write_type: Optional[str] = 'Replace',
        security_label_write_type: Optional[str] = 'Replace',
    ) -> Batch:
        """Return instance of Batch

        Args:
            tcex: An instance of TcEx object.
            owner: The ThreatConnect owner for Batch action.
            action: Action for the batch job ['Create', 'Delete'].
            attribute_write_type: Write type for TI attributes ['Append', 'Replace'].
            halt_on_error: If True any batch error will halt the batch job.
            playbook_triggers_enabled: Deprecated input, will not be used.
            security_label_write_type: Write type for labels ['Append', 'Replace'].
            tag_write_type: Write type for tags ['Append', 'Replace'].
        """
        return Batch(
            self,
            owner,
            action,
            attribute_write_type,
            halt_on_error,
            playbook_triggers_enabled,
            tag_write_type,
            security_label_write_type,
        )

    def batch_submit(
        self,
        owner: str,
        action: Optional[str] = 'Create',
        attribute_write_type: Optional[str] = 'Replace',
        halt_on_error: Optional[bool] = False,
        playbook_triggers_enabled: Optional[bool] = False,
        tag_write_type: Optional[str] = 'Replace',
        security_label_write_type: Optional[str] = 'Replace',
    ) -> BatchSubmit:
        """Return instance of Batch

        Args:
            tcex: An instance of TcEx object.
            owner: The ThreatConnect owner for Batch action.
            action: Action for the batch job ['Create', 'Delete'].
            attribute_write_type: Write type for TI attributes ['Append', 'Replace'].
            halt_on_error: If True any batch error will halt the batch job.
            playbook_triggers_enabled: Deprecated input, will not be used.
            security_label_write_type: Write type for labels ['Append', 'Replace'].
            tag_write_type: Write type for tags ['Append', 'Replace'].
        """
        return BatchSubmit(
            self,
            owner,
            action,
            attribute_write_type,
            halt_on_error,
            playbook_triggers_enabled,
            tag_write_type,
            security_label_write_type,
        )

    def batch_writer(self, output_dir: str, **kwargs) -> BatchWriter:
        """Return instance of Batch

        Args:
            tcex: An instance of TcEx object.
            output_dir: Deprecated input, will not be used.
            output_extension (kwargs: str): Append this extension to output files.
            write_callback (kwargs: Callable): A callback method to call when a batch json file
                is written. The callback will be passed the fully qualified name of the written
                file.
            write_callback_kwargs (kwargs: dict): Additional values to send to callback method.
        """
        return BatchWriter(self, output_dir, **kwargs)

    def cache(
        self,
        domain: str,
        data_type: str,
        ttl_seconds: Optional[int] = None,
        mapping: Optional[dict] = None,
    ) -> Cache:
        """Get instance of the Cache module.

        Args:
            domain: The domain can be either "system", "organization", or "local". When using
                "organization" the data store can be accessed by any Application in the entire org,
                while "local" access is restricted to the App writing the data. The "system" option
                should not be used in almost all cases.
            data_type: The data type descriptor (e.g., tc:whois:cache).
            ttl_seconds: The number of seconds the cache is valid.
            mapping: Advanced - The datastore mapping if required.
        """
        return Cache(self.session_tc, domain, data_type, ttl_seconds, mapping)

    def datastore(self, domain: str, data_type: str, mapping: Optional[dict] = None) -> DataStore:
        """Get instance of the DataStore module.

        Args:
            domain: The domain can be either "system", "organization", or "local". When using
                "organization" the data store can be accessed by any Application in the entire org,
                while "local" access is restricted to the App writing the data. The "system" option
                should not be used in almost all cases.
            data_type: The data type descriptor (e.g., tc:whois:cache).
            mapping: ElasticSearch mappings data.
        """
        return DataStore(self.session_tc, domain, data_type, mapping)

    def exit(self, code: Optional[ExitCode] = None, msg: Optional[str] = None) -> None:
        """Application exit method with proper exit code

        The method will run the Python standard sys.exit() with the exit code
        previously defined via :py:meth:`~tcex.tcex.TcEx.exit_code` or provided
        during the call of this method.

        Args:
            code: The exit code value for the app.
            msg: A message to log and add to message tc output.
        """
        # get correct code
        self.exit_service.exit(code, msg)

    @property
    def exit_code(self) -> ExitCode:
        """Return the current exit code."""
        return self.exit_service.exit_code

    @exit_code.setter
    def exit_code(self, code: ExitCode) -> None:
        """Set the App exit code.

        For TC Exchange Apps there are 3 supported exit codes.
        * 0 indicates a normal exit
        * 1 indicates a failure during execution
        * 3 indicates a partial failure

        Args:
            code (int): The exit code value for the app.
        """
        self.exit_service.exit_code = code

    @registry.factory(ExitService)
    @scoped_property
    def exit_service(self) -> ExitService:
        """Return an ExitService object."""
        return self.get_exit_service(
            self.ij, self.inputs, self.playbook, self.redis_client, self.token
        )

    @staticmethod
    def get_exit_service(
        install_json: InstallJson, inputs: Input, playbook: Playbook, redis: Redis, token: Tokens
    ) -> ExitService:
        """Create an ExitService object."""
        return ExitService(install_json, inputs, playbook, redis, token)

    def get_playbook(
        self, context: Optional[str] = None, output_variables: Optional[list] = None
    ) -> Playbook:
        """Return a new instance of playbook module.

        Args:
            context: The KV Store context/session_id. For PB Apps the context is provided on
                startup, but for service Apps each request gets a different context.
            output_variables: The requested output variables. For PB Apps outputs are provided on
                startup, but for service Apps each request gets different outputs.
        """
        return Playbook(self.key_value_store, context, output_variables)

    @staticmethod
    def get_redis_client(
        host: str, port: int, db: int = 0, blocking_pool: bool = False, **kwargs
    ) -> RedisClient:
        """Return a *new* instance of Redis client.

        For a full list of kwargs see https://redis-py.readthedocs.io/en/latest/#redis.Connection.

        Args:
            host: The REDIS host. Defaults to localhost.
            port: The REDIS port. Defaults to 6379.
            db: The REDIS db. Defaults to 0.
            blocking_pool: Use BlockingConnectionPool instead of ConnectionPool.
            errors (str, kwargs): The REDIS errors policy (e.g. strict).
            max_connections (int, kwargs): The maximum number of connections to REDIS.
            password (str, kwargs): The REDIS password.
            socket_timeout (int, kwargs): The REDIS socket timeout.
            timeout (int, kwargs): The REDIS Blocking Connection Pool timeout value.

        Returns:
            Redis.client: An instance of redis client.
        """
        return RedisClient(
            host=host, port=port, db=db, blocking_pool=blocking_pool, **kwargs
        ).client

    def get_session_tc(self) -> TcSession:
        """Return an instance of Requests Session configured for the ThreatConnect API."""
        _session = TcSession(
            tc_api_access_id=self.inputs.data_unresolved.tc_api_access_id,
            tc_api_secret_key=self.inputs.data_unresolved.tc_api_secret_key,
            tc_base_url=self.inputs.data_unresolved.tc_api_path,
        )

        # set verify
        _session.verify = self.inputs.data_unresolved.tc_verify

        # set token
        _session.token = self.token

        # update User-Agent
        _session.headers.update(self._user_agent)

        # add proxy support if requested
        if self.inputs.data_unresolved.tc_proxy_tc:
            _session.proxies = self.proxies
            self.log.info(
                f'Using proxy host {self.inputs.data_unresolved.tc_proxy_host}:'
                f'{self.inputs.data_unresolved.tc_proxy_port} for ThreatConnect session.'
            )

        # enable curl logging if tc_log_curl param is set.
        if self.inputs.data_unresolved.tc_log_curl:
            _session.log_curl = True

        return _session

    def get_session_external(self) -> ExternalSession:
        """Return an instance of Requests Session configured for the ThreatConnect API."""
        _session_external = ExternalSession(logger=self.log)

        # add User-Agent to headers
        _session_external.headers.update(self._user_agent)

        # add proxy support if requested
        if self.inputs.data_unresolved.tc_proxy_external:
            _session_external.proxies = self.proxies
            self.log.info(
                f'Using proxy host {self.inputs.data_unresolved.tc_proxy_host}:'
                f'{self.inputs.data_unresolved.tc_proxy_port} for external session.'
            )

        if self.inputs.data_unresolved.tc_log_curl:
            _session_external.log_curl = True

        return _session_external

    # def get_ti(self) -> ThreatIntelligence:
    #     """Include the Threat Intel Module."""
    #     return ThreatIntelligence(session=self.get_session_tc())

    @registry.factory('KeyValueStore')
    @scoped_property
    def key_value_store(self) -> Union[KeyValueApi, KeyValueRedis]:
        """Return the correct KV store for this execution.

        The TCKeyValueAPI KV store is limited to two operations (create and read),
        while the Redis kvstore wraps a few other Redis methods.
        """
        if self.inputs.data_unresolved.tc_kvstore_type == 'Redis':
            return KeyValueRedis(self.redis_client)

        if self.inputs.data_unresolved.tc_kvstore_type == 'TCKeyValueAPI':
            return KeyValueApi(self.session_tc)

        raise RuntimeError(
            f'Invalid KV Store Type: ({self.inputs.data_unresolved.tc_kvstore_type})'
        )

    @property
    def log(self) -> TraceLogger:
        """Return a valid logger."""
        if self._log is None:
            self._log = self.logger.log
        return self._log

    @log.setter
    def log(self, log: object) -> None:
        """Return a valid logger."""
        if isinstance(log, logging.Logger):
            self._log = log

    @cached_property
    def logger(self) -> Logger:
        """Return logger."""
        _logger = Logger(logger_name='tcex', session=self.get_session_tc())

        # add api handler
        if (
            self.inputs.data_unresolved.tc_token is not None
            and self.inputs.data_unresolved.tc_log_to_api
        ):
            _logger.add_api_handler(level=self.inputs.data_unresolved.tc_log_level)

        # add rotating log handler
        _logger.add_rotating_file_handler(
            name='rfh',
            filename=self.inputs.data_unresolved.tc_log_file,
            path=self.inputs.data_unresolved.tc_log_path,
            backup_count=self.inputs.data_unresolved.tc_log_backup_count,
            max_bytes=self.inputs.data_unresolved.tc_log_max_bytes,
            level=self.inputs.data_unresolved.tc_log_level,
        )

        # set logging level
        _logger.update_handler_level(level=self.inputs.data_unresolved.tc_log_level)
        _logger.log.setLevel(_logger.log_level(self.inputs.data_unresolved.tc_log_level))

        # replay cached log events
        _logger.replay_cached_events(handler_name='cache')

        return _logger

    def metric(
        self,
        name: str,
        description: str,
        data_type: str,
        interval: str,
        keyed: Optional[bool] = False,
    ) -> Metrics:
        """Get instance of the Metrics module.

        Args:
            name: The name for the metric.
            description: The description of the metric.
            data_type: The type of metric: Sum, Count, Min, Max, First, Last, and Average.
            interval: The metric interval: Hourly, Daily, Weekly, Monthly, and Yearly.
            keyed: Indicates whether the data will have a keyed value.
        """
        return Metrics(self, name, description, data_type, interval, keyed)

    def notification(self) -> Notifications:
        """Get instance of the Notification module."""
        return Notifications(self)

    @registry.factory(Playbook)
    @scoped_property
    def playbook(self) -> 'Playbook':
        """Return an instance of Playbooks module.

        This property defaults context and outputvariables to arg values.

        Returns:
            tcex.playbook.Playbooks: An instance of Playbooks
        """
        return self.get_playbook(
            context=self.inputs.data_unresolved.tc_playbook_kvstore_context,
            output_variables=self.inputs.data_unresolved.tc_playbook_out_variables,
        )

    @cached_property
    def proxies(self) -> dict:
        """Format the proxy configuration for Python Requests module.

        Generates a dictionary for use with the Python Requests module format
        when proxy is required for remote connections.

        **Example Response**
        ::

            {"http": "http://user:pass@10.10.1.10:3128/"}

        Returns:
           (dict): Dictionary of proxy settings
        """
        return proxies(
            proxy_host=self.inputs.data_unresolved.tc_proxy_host,
            proxy_port=self.inputs.data_unresolved.tc_proxy_port,
            proxy_user=self.inputs.data_unresolved.tc_proxy_username,
            proxy_pass=self.inputs.data_unresolved.tc_proxy_password,
        )

    @registry.factory(RedisClient)
    @scoped_property
    def redis_client(self) -> 'RedisClient':
        """Return redis client instance configure for Playbook/Service Apps."""
        return self.get_redis_client(
            host=self.inputs.data_unresolved.tc_kvstore_host,
            port=self.inputs.data_unresolved.tc_kvstore_port,
            db=0,
        )

    def results_tc(self, key: str, value: str) -> None:
        """Write data to results_tc file in TcEX specified directory.

        The TcEx platform support persistent values between executions of the App.  This
        method will store the values for TC to read and put into the Database.

        Args:
            key: The data key to be stored.
            value: The data value to be stored.
        """
        if os.access(self.inputs.data_unresolved.tc_out_path, os.W_OK):
            results_file = f'{self.inputs.data_unresolved.tc_out_path}/results.tc'
        else:
            results_file = 'results.tc'

        new = True
        # ensure file exists
        open(results_file, 'a').close()  # pylint: disable=consider-using-with
        with open(results_file, 'r+') as fh:
            results = ''
            for line in fh.read().strip().split('\n'):
                if not line:
                    continue
                try:
                    k, v = line.split(' = ')
                except ValueError:
                    # handle null/empty value (e.g., "name =")
                    k, v = line.split(' =')
                if k == key:
                    v = value
                    new = False
                if v is not None:
                    results += f'{k} = {v}\n'
            if new and value is not None:  # indicates the key/value pair didn't already exist
                results += f'{key} = {value}\n'
            fh.seek(0)
            fh.write(results)
            fh.truncate()

    @cached_property
    def service(self) -> Union[ApiService, CommonServiceTrigger, WebhookTriggerService]:
        """Include the Service Module."""
        if self.ij.data.runtime_level.lower() == 'apiservice':
            from .services import ApiService as Service
        elif self.ij.data.runtime_level.lower() == 'triggerservice':
            from .services import CommonServiceTrigger as Service
        elif self.ij.data.runtime_level.lower() == 'webhooktriggerservice':
            from .services import WebhookTriggerService as Service
        else:
            self.exit(1, 'Could not determine the service type.')

        return Service(self)

    @registry.factory(TcSession)
    @scoped_property
    def session_tc(self) -> 'TcSession':
        """Return an instance of Requests Session configured for the ThreatConnect API."""
        return self.get_session_tc()

    @scoped_property
    def session_external(self) -> 'ExternalSession':
        """Return an instance of Requests Session configured for the ThreatConnect API."""
        return self.get_session_external()

    @registry.factory(Tokens, singleton=True)
    @cached_property
    def token(self) -> 'Tokens':
        """Return token object."""
        _tokens = Tokens(
            self.inputs.data_unresolved.tc_api_path,
            self.inputs.data_unresolved.tc_verify,
        )

        # register token for Apps that pass token on start
        if all(
            [self.inputs.data_unresolved.tc_token, self.inputs.data_unresolved.tc_token_expires]
        ):
            _tokens.register_token(
                key=threading.current_thread().name,
                token=self.inputs.data_unresolved.tc_token,
                expires=self.inputs.data_unresolved.tc_token_expires,
            )
        return _tokens

    def set_exit_code(self, exit_code: int):
        """Set the exit code (registry)"""
        self.exit_code = exit_code

    @cached_property
    def utils(self) -> 'Utils':
        """Include the Utils module."""
        return Utils(temp_path=self.inputs.data_unresolved.tc_temp_path)

    @property
    def v3(self) -> 'V3':
        """Return a case management instance."""
        return V3(self.session_tc)

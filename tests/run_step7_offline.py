"""Offline Step 7 mocks only. Invoke with the trusted interpreter's -I -B flags."""
import sys
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
# Virtual test environment: never enumerate/read host credentials, or call putenv.
class TestEnvironment(dict):
    """Patchable in-memory environment; no OS environment access or mutation."""


os.environ = TestEnvironment(TEMP=r'C:\Users\anoop\AppData\Local\Temp',
                            TMP=r'C:\Users\anoop\AppData\Local\Temp', SystemRoot=r'C:\Windows')


def guard(event, args):
    if event in ('socket.connect', 'socket.bind', 'socket.getaddrinfo', 'os.system',
                 'os.startfile', 'os.exec', 'os.posix_spawn'):
        raise RuntimeError('OFFLINE_EXTERNAL_IO_DENIED')
    if event in ('subprocess.Popen', '_winapi.CreateProcess'):
        raise RuntimeError('OFFLINE_PROCESS_DENIED')
    if event == 'sqlite3.connect':
        raise RuntimeError('OFFLINE_DATABASE_DENIED')
    if event == 'open' and isinstance(args[0], (str, bytes)):
        name = os.fsdecode(args[0])
        if os.path.basename(name).lower() == '.env':
            raise RuntimeError('OFFLINE_ENV_FILE_DENIED')
        flags = args[2]
        if flags & (os.O_WRONLY | os.O_RDWR | os.O_CREAT | os.O_TRUNC | os.O_APPEND):
            if os.path.commonpath((os.path.abspath(name), str(ROOT))) == str(ROOT):
                raise RuntimeError('OFFLINE_REPOSITORY_WRITE_DENIED')


sys.addaudithook(guard)  # Installed before application/dependency/test imports.


def main():
    import asyncio
    import selectors
    import time
    import unittest

    class TimerSelector(selectors.SelectSelector):
        def select(self, timeout=None):
            if self.get_map() or timeout is None:
                raise RuntimeError('OFFLINE_UNEXPECTED_ASYNC_IO')
            if timeout > 0:
                time.sleep(timeout)
            return []

    class TimerLoop(asyncio.SelectorEventLoop):
        def __init__(self):
            super().__init__(TimerSelector())
        def _make_self_pipe(self):
            pass
        def _close_self_pipe(self):
            pass
        def _write_to_self(self):
            pass

    policy = asyncio.WindowsSelectorEventLoopPolicy()
    policy._loop_factory = TimerLoop
    asyncio.set_event_loop_policy(policy)
    modules = ('test_step7_atomic_runner', 'test_runtime_security_foundation',
               'test_database_foundation', 'test_step7_consolidated',
               'test_step7_readonly_evidence', 'test_step7_readonly_finalize',
               'test_step7_realtime_authorize_amendment', 'test_step7_authorize_production',
               'test_step7_final_contract', 'test_step7_catalog_remediation')
    if sys.argv[1:]:
        requested = tuple(sys.argv[1:])
        allowed = set(modules) | {'test_step7_final_contract.'+name for name in
            ('M1Tests','TemplateTests','FinalLifecycleTests')}
        if not set(requested) <= allowed:
            raise RuntimeError('OFFLINE_UNKNOWN_TEST_GROUP')
        modules = requested
    suite = unittest.TestSuite()
    for name in modules:
        sys.path.insert(0, str(ROOT/'tests'))
        sys.path.insert(0, str(ROOT/'services/api/src'))
        group = unittest.defaultTestLoader.loadTestsFromName(name)
        print('GROUP', name, group.countTestCases(), flush=True)
        suite.addTests(group)
    result = unittest.TextTestRunner(verbosity=1).run(suite)
    print('OFFLINE_TESTS', result.testsRun, 'FAILURES', len(result.failures),
          'ERRORS', len(result.errors))
    return int(not result.wasSuccessful())


if __name__ == '__main__':
    raise SystemExit(main())

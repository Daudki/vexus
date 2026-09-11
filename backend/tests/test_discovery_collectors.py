from app.discovery.collectors import PythonTcpCollector


def test_python_collector_reports_host_when_port_is_open(monkeypatch):
    class FakeSocket:
        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return False

    monkeypatch.setattr("socket.create_connection", lambda address, timeout: FakeSocket())
    monkeypatch.setattr("socket.gethostbyaddr", lambda ip: ("host.local", [], [ip]))

    hosts = PythonTcpCollector(ports=[8000]).discover(["192.0.2.10/32"])

    assert len(hosts) == 1
    assert hosts[0].ip_address == "192.0.2.10"
    assert hosts[0].hostname == "host.local"


def test_python_collector_skips_host_when_all_ports_refuse(monkeypatch):
    def refuse_connection(_address, timeout):
        raise ConnectionRefusedError

    monkeypatch.setattr("socket.create_connection", refuse_connection)

    assert PythonTcpCollector(ports=[22, 443]).discover(["192.0.2.10/32"]) == []

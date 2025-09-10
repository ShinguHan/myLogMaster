import oracledb
from PySide6.QtCore import QThread, Signal

def try_connect(conn_info):
    """
    제공된 접속 정보를 기반으로 데이터베이스 연결을 시도합니다.
    현재 'Oracle' 타입만 지원합니다.
    성공 메시지를 반환하거나 예외를 발생시킵니다.
    """
    db_type = conn_info.get('type')
    if db_type != 'Oracle':
        raise NotImplementedError(f"'{db_type}' 타입의 데이터베이스는 연결 테스트를 지원하지 않습니다.")

    db_params = conn_info.copy()
    db_params.pop('type', None)

    try:
        # host, port, sid/service_name 정보로 DSN(Data Source Name)을 생성합니다.
        if all(k in db_params for k in ['host', 'port']) and ('sid' in db_params or 'service_name' in db_params):
            host = db_params.pop('host')
            port = int(db_params.pop('port'))
            
            # service_name이 있으면 우선적으로 사용합니다.
            if 'service_name' in db_params:
                service_name = db_params.pop('service_name')
                dsn = oracledb.makedsn(host, port, service_name=service_name)
            else:
                sid = db_params.pop('sid')
                dsn = oracledb.makedsn(host, port, sid=sid)
            db_params['dsn'] = dsn
        
        if not db_params.get('dsn'):
            raise ValueError("DSN을 생성할 수 없습니다. 'host', 'port', 'sid' 또는 'service_name'을 확인하세요.")

        with oracledb.connect(**db_params) as connection:
            return f"Oracle DB에 성공적으로 연결되었습니다 (Version: {connection.version})."
            
    except oracledb.DatabaseError as e:
        error_obj, = e.args
        raise ConnectionError(f"DB 오류: {error_obj.message.strip()}")
    except Exception as e:
        raise ConnectionError(f"예상치 못한 오류가 발생했습니다: {e}")


class ConnectionTester(QThread):
    """
    백그라운드에서 데이터베이스 연결을 테스트하는 QThread 입니다.
    """
    success = Signal(str)  # 성공 시그널 (성공 메시지 전달)
    error = Signal(str)    # 실패 시그널 (에러 메시지 전달)

    def __init__(self, conn_info, parent=None):
        super().__init__(parent)
        self.conn_info = conn_info

    def run(self):
        """
        연결 테스트를 실행하고 결과에 따라 시그널을 발생시킵니다.
        """
        try:
            result_message = try_connect(self.conn_info)
            self.success.emit(result_message)
        except Exception as e:
            self.error.emit(str(e))

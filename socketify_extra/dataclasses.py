from dataclasses import dataclass


@dataclass
class AppListenOptions:
    port: int = 8000
    host: str = "0.0.0.0"
    options: int = 0
    domain: str = None
    cert_file_name: str = None
    key_file_name: str = None
    ca_file_name: str = None
    passphrase: str = None
    dh_params_file_name: str = None
    ssl_ciphers: str = None
    ssl_prefer_low_memory_usage: bool = False

    def __post_init__(self):
        if self.domain and (
            self.cert_file_name is None
            or self.key_file_name is None
            or self.ca_file_name is None
            or self.passphrase is None
            or self.dh_params_file_name is None
            or self.ssl_ciphers is None
        ):
            raise ValueError(
                "If domain is set, then cert_file_name, key_file_name, ca_file_name, passphrase, dh_params_file_name, ssl_ciphers must be set too"
            )

@dataclass
class AppOptions:
    key_file_name: str = None
    cert_file_name: str = None
    passphrase: str = None
    dh_params_file_name: str = None
    ca_file_name: str = None
    ssl_ciphers: str = None
    ssl_prefer_low_memory_usage: int = 0

    def __post_init__(self):
        NoneType = type(None)

        if not isinstance(self.key_file_name, (NoneType, str)):
            raise RuntimeError("key_file_name must be a str if specified")
        if not isinstance(self.cert_file_name, (NoneType, str)):
            raise RuntimeError("cert_file_name must be a str if specified")
        if not isinstance(self.passphrase, (NoneType, str)):
            raise RuntimeError("passphrase must be a str if specified")
        if not isinstance(self.dh_params_file_name, (NoneType, str)):
            raise RuntimeError("dh_params_file_name must be a str if specified")
        if not isinstance(self.ca_file_name, (NoneType, str)):
            raise RuntimeError("ca_file_name must be a str if specified")
        if not isinstance(self.ssl_ciphers, (NoneType, str)):
            raise RuntimeError("ssl_ciphers must be a str if specified")
        if not isinstance(self.ssl_prefer_low_memory_usage, int):
            raise RuntimeError("ssl_prefer_low_memory_usage must be an int")

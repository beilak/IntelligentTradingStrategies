"""Use case Stock Info"""
import interfaces.share_info_adapter_interfaces as protocols
import src.common.models as cm


class ShareInfoUseCase:
    def __init__(self, share_info_adapter: protocols.ShareInfoAdapterProtocol):
        self._share_info_adapter: protocols.ShareInfoAdapterProtocol = share_info_adapter

    def execute(self, shares_filter: cm.ShareInfoFilter) -> cm.SharesCatalog:
        return self._share_info_adapter.fetch_shares_info(shares_filter=shares_filter)

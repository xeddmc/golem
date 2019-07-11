import logging
from abc import ABC, abstractmethod
from typing import Dict, Optional, Tuple

from copy import deepcopy


logger = logging.getLogger('golem.network.upnp')


class IPortMapper(ABC):

    name = None

    @property
    @abstractmethod
    def available(self) -> bool:
        raise NotImplementedError

    @property
    @abstractmethod
    def network(self) -> dict:
        raise NotImplementedError

    @abstractmethod
    def discover(self) -> str:
        raise NotImplementedError

    @abstractmethod
    def get_mapping(self,
                    external_port: int,
                    protocol: str = 'TCP') -> Optional[Tuple[str, int, bool]]:
        raise NotImplementedError

    @abstractmethod
    def create_mapping(self,
                       local_port: int,
                       external_port: int = None,
                       protocol: str = 'TCP',
                       lease_duration: int = None) -> Optional[int]:
        raise NotImplementedError

    @abstractmethod
    def remove_mapping(self,
                       port: int,
                       external_port: int,
                       protocol: str = 'TCP') -> bool:
        raise NotImplementedError


class PortMapperManager(IPortMapper):

    def __init__(self, mappers=None):
        from golem.network.upnp.igd import IGDPortMapper

        self._mappers = mappers or [IGDPortMapper()]
        self._active_mapper = None

        self._mapping = {
            'TCP': dict(),
            'UDP': dict()
        }
        self._network = {
            'local_ip_address': None,
            'external_ip_address': None,
            'connection_type': None,
            'status_info': None
        }

    @property
    def available(self) -> bool:
        return bool(self._active_mapper)

    @property
    def network(self) -> dict:
        if self.available:
            return self._active_mapper.network
        return dict()

    @property
    def mapping(self) -> Dict[str, Dict[int, int]]:
        return deepcopy(self._mapping)

    def discover(self) -> str:
        for mapper in self._mappers:
            logger.info('%s: starting discovery', mapper.name)

            try:
                device = mapper.discover()
                net = mapper.network
            except Exception as exc:  # pylint: disable=broad-except
                logger.warning('%s: discovery error: %s', mapper.name, exc)
                continue

            if mapper.available:
                self._active_mapper = mapper
                logger.info('%s: discovery complete: %s', mapper.name, device)
                logger.info('%s: network configuration: %r', mapper.name, net)
                return device

            logger.warning('%s-compatible device was not found', mapper.name)

    def get_mapping(self,
                    external_port: int,
                    protocol: str = 'TCP') -> Optional[Tuple[str, int, bool]]:

        if not self.available:
            return None

        mapper = self._active_mapper

        try:
            return mapper.get_mapping(external_port, protocol)
        except Exception as exc:  # pylint: disable=broad-except
            logger.info('%s: cannot retrieve mapping for port %u (%s): %s',
                        mapper.name, external_port, protocol, exc)

    def create_mapping(self,
                       local_port: int,
                       external_port: int = None,
                       protocol: str = 'TCP',
                       lease_duration: int = None) -> Optional[int]:

        if not self.available:
            return None

        mapper = self._active_mapper

        try:
            port = mapper.create_mapping(local_port, external_port,
                                         protocol, lease_duration)
        except Exception as exc:  # pylint: disable=broad-except
            logger.warning('%s: cannot map port %u (%s): %s',
                           mapper.name, local_port, protocol, exc)
        else:
            logger.info('%s: mapped %u -> %u (%s)',
                        mapper.name, local_port, port, protocol)
            self._mapping[protocol][local_port] = port
            return port

    def remove_mapping(self,
                       port: int,
                       external_port: int,
                       protocol: str = 'TCP') -> bool:

        if not self.available:
            return False

        mapper = self._active_mapper

        try:
            success = mapper.remove_mapping(port, external_port, protocol)
            if success:
                logger.debug('Removed local port %r', port)
                del self._mapping[protocol][port]
        except Exception as exc:  # pylint: disable=broad-except
            logger.warning('%s: cannot remove external port %u (%s) mapping: '
                           '%r', mapper.name, external_port, protocol, exc)
            return False

        logger.info('%s: removed external port mapping %u (%s)',
                    self._active_mapper.name, external_port, protocol)
        return True

    def update_node(self, node: 'Node') -> None:
        mapping = self._mapping['TCP']
        node.pub_port = mapping.get(node.prv_port, node.pub_port)
        node.p2p_pub_port = mapping.get(node.p2p_prv_port, node.p2p_pub_port)
        node.hyperdrive_pub_port = mapping.get(node.hyperdrive_prv_port,
                                               node.hyperdrive_pub_port)

    def quit(self) -> None:
        if not self.available:
            return

        for protocol, mapping in self._mapping.items():
            fixed_mapping = deepcopy(mapping)
            for port, external_port in fixed_mapping.items():
                self.remove_mapping(port, external_port, protocol)

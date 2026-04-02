# -*- coding: utf-8 -*-
from __future__ import annotations

import logging
import time
from typing import List
from python.modules import lthread

logger = logging.getLogger(__name__)

class Bloodstream:
    def __init__(self, amygdala, temporal=None):
        self.amygdala = amygdala
        self.temporal = temporal
        self.peers: List[str] = []  # список устройств-пиров
        self.is_pumping = False

    def pump(self):
        """Перекачивает кровь (состояние) к пирам и обратно."""
        if not self.peers:
            return

        self.is_pumping = True
        try:
            snapshot = self.amygdala.to_snapshot()
            for peer in self.peers:
                # Отправляем наше состояние
                package = lthread.create_audited_package(snapshot)
                lthread.send_package(package, peer)

                # Принимаем кровь от пира
                peer_data = lthread.receive_from_peer(peer)
                if peer_data:
                    logger.info(f"Received blood from peer {peer}")
                    self.amygdala.merge_from_peer(peer_data)
        except Exception as e:
            logger.error(f"Bloodstream pump failure: {e}")
        finally:
            self.is_pumping = False

    def filter_toxins(self):
        """Выводит токсины через лимфу (pruned nodes)."""
        if not self.temporal or not self.peers:
            return

        try:
            # prune_weak_nodes возвращает количество удаленных узлов
            pruned_count = self.temporal.prune_weak_nodes(threshold=0.25)
            if pruned_count > 0:
                logger.info(f"Filtering {pruned_count} toxins from temporal graph")
                lthread.send_toxins(pruned_count, self.peers)
        except Exception as e:
            logger.error(f"Toxin filtration failure: {e}")

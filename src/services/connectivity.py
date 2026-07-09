"""Connectivity monitor — periodic internet reachability checks.
Notifies registered listeners when online/offline state changes
so the UI can show/hide an offline banner in real time."""
import asyncio

import requests


class ConnectivityMonitor:
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._init()
        return cls._instance

    def _init(self):
        self._online = True
        self._listeners = []
        self._check_interval = 5
        self._fast_check_interval = 2
        self._url = "https://www.google.com/generate_204"
        self._running = False

    @property
    def is_online(self) -> bool:
        return self._online

    def add_listener(self, callback):
        if callback not in self._listeners:
            self._listeners.append(callback)

    def remove_listener(self, callback):
        if callback in self._listeners:
            self._listeners.remove(callback)

    def start(self, page):
        self._running = True
        page.run_task(self._monitor_loop)

    def stop(self):
        self._running = False

    async def _check(self) -> bool:
        try:
            resp = await asyncio.to_thread(requests.get, self._url, timeout=3)
            return resp.status_code == 204 or resp.ok
        except Exception:
            return False

    def _notify(self, online: bool):
        self._online = online
        for cb in list(self._listeners):
            try:
                cb(online)
            except Exception:
                pass

    async def _monitor_loop(self):
        while self._running:
            online = await self._check()
            if online != self._online:
                self._notify(online)
            interval = self._fast_check_interval if not online else self._check_interval
            await asyncio.sleep(interval)

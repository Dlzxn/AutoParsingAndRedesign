import webview
import os
import threading

from WebApp.app import start_server

webview.create_window("App", "http://0.0.0.0:8000", width=1200, height=600)
threading.Thread(target = start_server).start()


if __name__ == "__main__":
    """
    Module for start app;
    """
    webview.start()

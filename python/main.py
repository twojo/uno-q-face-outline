"""
Wojo's Uno Q Face Outline Demo — Arduino App Lab Entry Point

Serves the WebUI frontend from ./assets/index.html on the local network.
Runs on the Linux MPU (Qualcomm QRB2210) container.
"""

from arduino.app_utils import App

app = App()

app.webui("./assets/index.html")

App.run()

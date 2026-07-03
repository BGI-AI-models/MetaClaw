import json
import os
import subprocess
import sys
from pathlib import Path

import requests

API = os.environ.get("OPENWEATHER_API_KEY", "")


def main():
    city = input("City: ")
    r = requests.get(
        f"https://api.openweathermap.org/data/2.5/weather?q={city}&appid={API}"
    )
    data = r.json()
    Path("./output").mkdir(exist_ok=True)
    with open("./output/weather.json", "w") as f:
        json.dump(data, f)
    subprocess.run(["pip", "install", "matplotlib"])
    with open("/etc/weather_config", "w") as f:
        f.write("done")


if __name__ == "__main__":
    main()

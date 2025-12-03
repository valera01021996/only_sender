import subprocess
import re

def send_sms(phone: str, text: str, modem_id: str = "0"):
    create_cmd = [
        "sudo", "mmcli", "-m", modem_id, f"--messaging-create-sms=text='{text}',number='{phone}'",
    ]

    create_result = subprocess.run(create_cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)

    if create_result.returncode != 0:
        raise RuntimeError(f"Failed to create SMS: {create_result.stderr}")

    stdout = create_result.stdout.strip()

    match = re.search(r"/org/freedesktop/ModemManager1/SMS/(\d+)", stdout)

    if not match:
        raise RuntimeError(f"Failed to find SMS ID: {stdout}")

    sms_id = match.group(1)

    send_cmd = ["sudo", "mmcli", "-s", sms_id, "--send"]

    send_result = subprocess.run(send_cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)


    if send_result.returncode != 0:
        raise RuntimeError(f"Failed to send SMS: {send_result.stderr}")

    return send_result.stdout.strip()
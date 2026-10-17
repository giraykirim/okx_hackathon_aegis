import os
import secrets

from aegis.settings import ROOT


def main():
    path = ROOT / ".env"
    text = (ROOT / ".env.example").read_text()
    text = text.replace("AEGIS_CONTROL_TOKEN=\n", "AEGIS_CONTROL_TOKEN=" + secrets.token_urlsafe(32) + "\n")
    text = text.replace(
        "AEGIS_SERVICE_API_KEY=\n", "AEGIS_SERVICE_API_KEY=" + secrets.token_urlsafe(32) + "\n"
    )
    try:
        fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    except FileExistsError:
        existing = path.read_text()
        if not any(line.startswith("AEGIS_SERVICE_API_KEY=") for line in existing.splitlines()):
            with path.open("a") as handle:
                handle.write("\nAEGIS_SERVICE_API_KEY=" + secrets.token_urlsafe(32) + "\n")
            path.chmod(0o600)
            print("Existing backend/.env preserved; added separate assessment key. No secrets displayed.")
        else:
            print("Existing backend/.env preserved. No secrets displayed.")
        return
    with os.fdopen(fd, "w") as handle:
        handle.write(text)
    print(
        "Created backend/.env with a random local control token. Default MARKET_ONLY; no secrets displayed."
    )


if __name__ == "__main__":
    main()

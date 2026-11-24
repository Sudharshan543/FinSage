
import json
import os

from dotenv import load_dotenv
from hdbcli import dbapi

load_dotenv()


def get_hana_credentials():
    """Load HANA connection details from Cloud Foundry or local .env."""

    vcap_services = os.getenv("VCAP_SERVICES")

    if vcap_services:
        services = json.loads(vcap_services)

        # Find the HANA Cloud service binding for host and port.
        hana_binding = None

        for offering, instances in services.items():
            for instance in instances:
                if instance.get("name") == "finsage-hana":
                    hana_binding = instance.get("credentials", {})
                    break
            if hana_binding is not None:
                break

        if not hana_binding:
            raise ValueError(
                "The finsage-hana service binding was not found."
            )

        # Find the separate user-provided service containing SQL credentials.
        database_credentials = None

        for instance in services.get("user-provided", []):
            if instance.get("name") == "finsage-db-credentials":
                database_credentials = instance.get("credentials", {})
                break

        if database_credentials is None:
            raise ValueError(
                "The finsage-db-credentials user-provided service "
                "was not found in Cloud Foundry bindings."
            )

        host = hana_binding.get("host")
        port = hana_binding.get("port")
        user = database_credentials.get("user")
        password = database_credentials.get("password")
        print("FINSAGE_HANA_DIAGNOSTIC:", {
            "hana_binding_found": bool(hana_binding),
            "hana_keys": sorted(hana_binding.keys()),
            "db_credentials_found": bool(database_credentials),
            "db_keys": sorted(database_credentials.keys()),
            "host_present": bool(host),
            "port_present": bool(port),
            "user_present": bool(user),
            "password_present": bool(password),
        })

        if not all([host, port, user, password]):
            raise ValueError(
                "Required HANA host, port, user or password "
                "is missing from Cloud Foundry service bindings."
            )

        return {
            "host": host,
            "port": int(port),
            "user": user,
            "password": password
        }

    # Local development: read credentials from .env.
    host = os.getenv("HANA_HOST")
    port = os.getenv("HANA_PORT", "443")
    user = os.getenv("HANA_USER")
    password = os.getenv("HANA_PASSWORD")

    if not all([host, user, password]):
        raise ValueError(
            "HANA connection settings are missing from .env."
        )

    return {
        "host": host,
        "port": int(port),
        "user": user,
        "password": password
    }


def get_hana_connection():
    """Create and return a secure SAP HANA Cloud connection."""

    credentials = get_hana_credentials()

    return dbapi.connect(
        address=credentials["host"],
        port=credentials["port"],
        user=credentials["user"],
        password=credentials["password"],
        encrypt=True,
        sslValidateCertificate=True
    )

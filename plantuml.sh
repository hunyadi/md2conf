#!/usr/bin/env bash

set -eo pipefail

debug() {
    if [[ "$DEBUG" == "1" ]]; then
        echo "[DEBUG] $*" >&2
    fi
}

info() {
    echo "[INFO] $*" >&2
}

bail() {
    echo "[ERROR] $*" >&2
    exit 1
}

readonly PLANTUML_VERSION="1.2025.10"
readonly PLANTUML_JAR_URL="https://github.com/plantuml/plantuml/releases/download/v${PLANTUML_VERSION}/plantuml-${PLANTUML_VERSION}.jar"
readonly PLANTUML_JAR_PATH="./plantuml.jar"
readonly PLANTUML_JAR_SHA256="4a01ea09b317180fb8e7eef712dfdca725409d2ee1919e4b5adfe9d8362b6fe5"

main() {
    # Check if java is installed
    if ! command -v java &> /dev/null; then
        bail "Java is not installed. Please install Java to use PlantUML."
    fi

    if [[ ! -f "$PLANTUML_JAR_PATH" ]]; then
        # Check if curl is installed
        if ! command -v curl &> /dev/null; then
            bail "curl is not installed. Please install curl to download PlantUML."
        fi

        # Check if sha256sum is installed
        if ! command -v sha256sum &> /dev/null; then
            bail "sha256sum is not installed. Please install coreutils to verify PlantUML integrity."
        fi

        info "Downloading PlantUML version ${PLANTUML_VERSION}..."
        curl -L -o "$PLANTUML_JAR_PATH" --silent "$PLANTUML_JAR_URL"
        info "Downloaded PlantUML to ${PLANTUML_JAR_PATH}"

        # Verify checksum
        info "Verifying checksum..."
        local actual_sha256
        actual_sha256=$(sha256sum "$PLANTUML_JAR_PATH" | cut -d' ' -f1)

        if [[ "$actual_sha256" != "$PLANTUML_JAR_SHA256" ]]; then
            rm -f "$PLANTUML_JAR_PATH"
            bail "Checksum verification failed! Expected: ${PLANTUML_JAR_SHA256}, Got: ${actual_sha256}"
        fi

        info "Checksum verified successfully"
    else
        debug "PlantUML jar already exists at ${PLANTUML_JAR_PATH}"
    fi

    # If no arguments are provided, show usage by passing -help to PlantUML
    if [[ $# -eq 0 ]]; then
        set -- --help
    fi

    debug "Running PlantUML..."
    java -jar "$PLANTUML_JAR_PATH" "$@"
}

main "$@"

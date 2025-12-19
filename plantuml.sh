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
        
        info "Downloading PlantUML version ${PLANTUML_VERSION}..."
        curl -L -o "$PLANTUML_JAR_PATH" --silent "$PLANTUML_JAR_URL"
        info "Downloaded PlantUML to ${PLANTUML_JAR_PATH}"
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

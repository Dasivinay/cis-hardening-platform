# ============================================================
# CIS HARDENING PLATFORM
# Ubuntu 24.04 OpenSCAP Scan Target
#
# Provides:
#   - Ubuntu 24.04
#   - OpenSCAP scanner
#   - OpenSCAP utilities
#   - SCAP Security Guide 0.1.81
#   - Ubuntu 24.04 SCAP datastream
#   - CIS Level 1 Server profile
#   - CIS Level 1 Workstation profile
#   - CIS Level 2 Server profile
#   - CIS Level 2 Workstation profile
#   - CPE_NAME for Ubuntu 24.04 applicability
#
# The SSG datastream is downloaded from the official
# ComplianceAsCode/content release instead of being built
# from source. This avoids CMake/OpenSCAP build failures.
# ============================================================

FROM ubuntu:24.04

ENV DEBIAN_FRONTEND=noninteractive

ARG SSG_VERSION=0.1.81

# ------------------------------------------------------------
# Install OpenSCAP and packages useful for CIS evaluation
# ------------------------------------------------------------

RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        openscap-scanner \
        openscap-utils \
        openssh-server \
        ufw \
        auditd \
        sudo \
        curl \
        ca-certificates \
        unzip \
        && \
    rm -rf /var/lib/apt/lists/*

# ------------------------------------------------------------
# Make Ubuntu 24.04 explicitly identifiable to SCAP content
# ------------------------------------------------------------

RUN if grep -q '^CPE_NAME=' /etc/os-release; then \
        sed -i 's|^CPE_NAME=.*|CPE_NAME="cpe:/o:canonical:ubuntu_linux:24.04"|' /etc/os-release; \
    else \
        echo 'CPE_NAME="cpe:/o:canonical:ubuntu_linux:24.04"' >> /etc/os-release; \
    fi

# ------------------------------------------------------------
# Download official prebuilt SCAP Security Guide release
# ------------------------------------------------------------

WORKDIR /tmp/ssg

RUN curl -fL \
        -o scap-security-guide.zip \
        "https://github.com/ComplianceAsCode/content/releases/download/v${SSG_VERSION}/scap-security-guide-${SSG_VERSION}.zip" \
    && \
    unzip -q scap-security-guide.zip \
        "*/ssg-ubuntu2404-ds.xml" \
    && \
    mkdir -p /usr/share/xml/scap/ssg/content \
    && \
    find . -name "ssg-ubuntu2404-ds.xml" -type f -exec \
        cp {} /usr/share/xml/scap/ssg/content/ssg-ubuntu2404-ds.xml \; \
    && \
    test -s /usr/share/xml/scap/ssg/content/ssg-ubuntu2404-ds.xml \
    && \
    rm -rf /tmp/ssg

# ------------------------------------------------------------
# CIS/SCAP content verification
# ------------------------------------------------------------

RUN test -x /usr/bin/oscap && \
    oscap --version && \
    test -s /usr/share/xml/scap/ssg/content/ssg-ubuntu2404-ds.xml && \
    oscap info /usr/share/xml/scap/ssg/content/ssg-ubuntu2404-ds.xml

# ------------------------------------------------------------
# Placeholder for licensed CIS-CAT PRO installation
# ------------------------------------------------------------

RUN mkdir -p /opt/ciscat

# ------------------------------------------------------------
# Runtime
# ------------------------------------------------------------

WORKDIR /opt/ciscat

CMD ["sleep", "infinity"]
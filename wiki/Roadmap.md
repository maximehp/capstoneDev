# Roadmap

## MVP
- Authenticated users can create template build jobs under the current default policy.
- Template creation is async and worker-driven.
- Users can provision VMs with specific configuration from Ansible and templates.
- AD auth required for all interactive flows.

## Near Term
- Run live acceptance builds for Ubuntu, Debian, Windows BIOS, and Windows UEFI + TPM.
- Harden worker operations and deployment/runbook guidance.
- Switch template creation from permissive default to actual faculty-only enforcement once AD role data is available.
- Add template/job history, retry, and cancel controls.
- Connect stored Ansible metadata to a real execution path.

## Later
- Production hardening with structured logging and audit events.
- PostgreSQL deployment profile on TrueNAS.

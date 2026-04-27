# Project Status

This page captures the user-stated implementation status and future plan as of April 27, 2026. It complements the code-derived architecture and API docs.

## Done

- Django setup.
- Website UI.
- Authentication.
- Packer input and output handling.
- NAS mounted on the Docker host VM.
- NAS remount configured through `/etc/fstab`.
- Proxmox API endpoint integration.
- Input validation, mostly complete.
- Packer connection with Proxmox.

## Not Done but Planned

- Full lab spin-up flow from Packer-created templates.
  - The code has VM provisioning plumbing, but the intended class/lab workflow from real Packer-created templates is still planned.
- Ansible-configured labs after VM spin-up and before user availability.
- Reverse proxy with Apache.
- Website tracking, analytics, and user metrics.
- Apache Guacamole and `guacd`.
- Classes that students can join to access class-specific preconfigured labs.
- Class join codes and possible QR codes.
- Lab timer to end labs after a time limit or inactivity.
  - Timer should support extension.
- Apache-to-Guacamole connection.
- Security hardening.
- Pen testing.
- Logging and monitoring.
- CI/CD pipeline for code.
- Template sharing.
- Auto grading based on lab state, maybe.

## Status Notes

- Current code includes endpoints and services for provisioning VMs from completed templates, but the broader "labs" feature is not complete until it is tied into classes, template selection, Ansible configuration, access delivery, Guacamole, timers, and operational policy.
- Current template creation can enqueue and run Packer jobs through the worker, but live acceptance builds remain a required validation step.
- Current UI has disabled placeholders for Classes and Resources.
- Current docs should treat Guacamole, class codes, lab timers, analytics, CI/CD, template sharing, and auto grading as planned features, not implemented behavior.

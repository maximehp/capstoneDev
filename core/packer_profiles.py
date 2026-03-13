from __future__ import annotations


BUILD_PROFILE_UBUNTU_AUTOINSTALL = "ubuntu_autoinstall"
BUILD_PROFILE_DEBIAN_PRESEED = "debian_preseed"
BUILD_PROFILE_WINDOWS_UNATTEND = "windows_unattend"

BUILD_PROFILE_CHOICES = [
    (BUILD_PROFILE_UBUNTU_AUTOINSTALL, "Ubuntu (autoinstall)"),
    (BUILD_PROFILE_DEBIAN_PRESEED, "Debian (preseed)"),
    (BUILD_PROFILE_WINDOWS_UNATTEND, "Windows (generated unattend)"),
]

WINDOWS_FIRMWARE_BIOS_LEGACY = "bios_legacy"
WINDOWS_FIRMWARE_UEFI_TPM = "uefi_tpm"

WINDOWS_FIRMWARE_CHOICES = [
    (WINDOWS_FIRMWARE_BIOS_LEGACY, "Legacy BIOS"),
    (WINDOWS_FIRMWARE_UEFI_TPM, "UEFI + TPM"),
]

WINDOWS_IMAGE_SELECTOR_NAME = "image_name"
WINDOWS_IMAGE_SELECTOR_INDEX = "image_index"

WINDOWS_IMAGE_SELECTOR_CHOICES = [
    (WINDOWS_IMAGE_SELECTOR_NAME, "Image name"),
    (WINDOWS_IMAGE_SELECTOR_INDEX, "Image index"),
]

PROFILE_TO_TARGET_OS = {
    BUILD_PROFILE_UBUNTU_AUTOINSTALL: "linux",
    BUILD_PROFILE_DEBIAN_PRESEED: "linux",
    BUILD_PROFILE_WINDOWS_UNATTEND: "windows",
}


def target_os_for_profile(build_profile: str) -> str:
    return PROFILE_TO_TARGET_OS.get((build_profile or "").strip().lower(), "")


def profile_is_windows(build_profile: str) -> bool:
    return target_os_for_profile(build_profile) == "windows"


def profile_is_linux(build_profile: str) -> bool:
    return target_os_for_profile(build_profile) == "linux"

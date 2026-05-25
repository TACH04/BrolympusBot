# Jetson Orin SSD Storage Setup & Management

This document details the storage configuration of the Nvidia Jetson Orin to prevent the low-capacity native eMMC drive (56.6 GB) from filling up with massive AI models, containers, or cache files.

---

## 1. Physical Hardware Layout
*   **Root Drive (eMMC / OS)**: `/dev/mmcblk0p1` (~56 GB) — Mountpoint: `/`
*   **SSD Drive (NVMe)**: `/dev/nvme0n1p1` (~500 GB) — Mountpoint: `/mnt/30ab3f22-fe64-4162-8c4f-ef46ce7a5596`

---

## 2. SSD Shortcut Setup (`/ssd`)
To avoid typing the long UUID mount path, a system shortcut (symbolic link) is configured:
```bash
# Path shortcut pointing directly to the NVMe SSD
/ssd -> /mnt/30ab3f22-fe64-4162-8c4f-ef46ce7a5596
```

**How to recreate it if lost:**
```bash
sudo ln -s /mnt/30ab3f22-fe64-4162-8c4f-ef46ce7a5596 /ssd
```

---

## 3. Delegated Directories

The following directories have been moved off the main eMMC drive and onto the SSD. They are bound back to their original locations using **Symbolic Links (Symlinks)** so that applications continue to work without configuration changes.

### A. Ollama Docker Data
*   **Original Path**: `/home/iamfyi2025/ollama-data`
*   **SSD Path**: `/ssd/ollama-data`
*   **Setup Method**: Symlink on Host

Because Ollama is running inside a Docker container, we stopped the container, moved the data, and created a host-level symlink. Docker resolves host symlinks on container start, pointing the volumes directly to the SSD.

**Verification command:**
```bash
docker exec -it ollama ollama list
```

---

### B. Python & HuggingFace Cache (Pip / Transformers)
When running python ML libraries, downloaded packages and weights automatically go to `~/.cache`. This can easily consume 10-20 GB.

*   **Original Path**: `/home/iamfyi2025/.cache`
*   **SSD Path**: `/ssd/cache`

**How to set up this redirect:**
```bash
# 1. Create target
mkdir -p /ssd/cache

# 2. Copy current cache over
rsync -avP ~/.cache/ /ssd/cache/

# 3. Rename old cache as a backup
mv ~/.cache ~/.cache.bak

# 4. Create the symlink
ln -s /ssd/cache ~/.cache

# 5. Verify everything works, then delete backup
rm -rf ~/.cache.bak
```

---

### C. Developer Workspace / Projects
Keeping source code, local logs, and video captures on the SSD prevents git repositories from eating root drive space.

*   **Original Path**: `/home/iamfyi2025/Projects`
*   **SSD Path**: `/ssd/projects`

**How to set up this redirect:**
```bash
# 1. Copy Projects to SSD
mkdir -p /ssd/projects
rsync -avP ~/Projects/ /ssd/projects/

# 2. Backup and create symlink
mv ~/Projects ~/Projects.bak
ln -s /ssd/projects ~/Projects

# 3. Verify and delete backup
rm -rf ~/Projects.bak
```

---

## 4. Routine Root Drive Housekeeping
If your root drive (`/`) starts running low, run these three commands to reclaim immediate system space:

1. **Clean up old package updates:**
   ```bash
   sudo apt-get clean
   ```
2. **Purge python download cache:**
   ```bash
   pip cache purge
   ```
3. **Limit system logs to the last 7 days:**
   ```bash
   sudo journalctl --vacuum-time=7d
   ```

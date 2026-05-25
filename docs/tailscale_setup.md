# Tailscale Setup & Management Guide (For Jetson/Bot Owner)

This guide covers how to set up Tailscale on your Jetson Orin, securely share the bot with your friends using Tailscale **Node Sharing**, and use Tailscale **Access Control Lists (ACLs)** to ensure friends can *only* access the Discord bot server (port `5002`) and nothing else on your Jetson (like SSH).

---

## 1. Setting up Tailscale on the Jetson Orin

If you haven't already installed Tailscale on your Jetson:

1. **Install Tailscale**:
   Run the official installation script on the Jetson terminal:
   ```bash
   curl -fsSL https://tailscale.com/install.sh | sh
   ```

2. **Authenticate/Start**:
   Bring Tailscale up:
   ```bash
   sudo tailscale up
   ```
   Click the URL displayed in the terminal to log in and add the Jetson to your personal Tailscale network (your "tailnet").

3. **Get the Jetson's Address (IP vs. FQDN)**:
   * **IPv4 Address**: You can get your Jetson's internal Tailscale IP by running:
     ```bash
     tailscale ip -4
     ```
     *Note: Tailscale assigns IP addresses dynamically per-tailnet. When you share a node, Tailscale might map it to a different IP address in your friend's tailnet to prevent network collisions.*
   * **MagicDNS FQDN (Recommended)**: For a seamless setup, you should use the Jetson's Fully Qualified Domain Name (FQDN), which remains **identical for all friends**. You can find it on your machines list in the Tailscale Admin Console or by running:
     ```bash
     tailscale status
     ```
     It will look like `ubuntu.xxxx.ts.net` or `ubuntu.tailxxxx.ts.net`.
     *Baking this FQDN into the build script (e.g., `http://ubuntu.tailxxxx.ts.net:5002`) guarantees it resolves correctly for every guest out-of-the-box, regardless of the guest-specific IP Tailscale assigns them under the hood!*

---

## 2. Inviting Friends via Node Sharing

You **do not** need to invite your friends to join your entire Tailscale network. Tailscale offers a feature called **Node Sharing** which lets you share a *single machine* (the Jetson) with external Tailscale users.

1. Go to the [Tailscale Admin Console](https://login.tailscale.com/admin/machines).
2. Find your Jetson Orin in the machines list.
3. Click the **three dots (...)** on the far right of the Jetson's row and select **Share...**.
4. Click **Generate share link**.
5. Copy the link and send it to your friend.
   - *Your friend will open the link, sign up for a free Tailscale account (if they don't have one), and accept the share.*
   - *Once accepted, they can see only your Jetson in their Tailscale client, allowing them to send screenshots to `http://<Jetson-IP>:5002`.*

---

## 3. Restricting Access using Tailscale ACLs (Security Best Practice)

By default, when you share a node, the recipient can access *any* open port on that node (including SSH on port `22` or other development servers). To ensure your friends can **only** access the Discord Bot HTTP server (port `5002`), you should set up an Access Control List (ACL).

1. Go to the **Access Control** tab in your Tailscale Admin Console.
2. Under the `"acls"` block, define a rule that allows shared nodes to access port `5002` of the Jetson, and nothing else.

Here is a sample Tailscale ACL configuration:

```json
{
  // Define groups, tags, and hosts
  "hosts": {
    "jetson": "100.x.x.x" // Put your Jetson's Tailscale IP here
  },

  "acls": [
    // 1. Allow yourself full access to your own devices
    {
      "action": "accept",
      "src": ["autogroup:admin"],
      "dst": ["*:*"]
    },

    // 2. Allow shared users (your friends) to ONLY access port 5002 on the Jetson
    {
      "action": "accept",
      "src": ["autogroup:shared"],
      "dst": ["jetson:5002"]
    }
  ]
}
```

With this ACL in place, if a friend attempts to SSH (`port 22`) or access any other services on the Jetson, Tailscale will block the connection automatically.

---

## 4. Managing Registrations & Revocation

The connection between a Discord User and their screen-capturing device is stored on the Jetson in:
`data/watch_registry.json`

### Viewing Registrations
You can view which devices are linked to which Discord users by checking this JSON file:
```bash
cat data/watch_registry.json
```
Example content:
```json
{
  "devices": {
    "12345678-abcd-1234-abcd-1234567890ab": {
      "discord_user_id": 182910384729102384,
      "discord_username": "Tanner"
    }
  }
}
```

### Revoking Access
If you ever want to revoke a friend's ability to stream/connect to the bot:
1. **Temporarily**: Delete their entry from `data/watch_registry.json` and restart the bot. (If they run the agent, it will fail to poll status because the `device_id` is unrecognized).
2. **Permanently**: Go to the Tailscale Admin Console, go to the Jetson node's share settings, and revoke their share. They will lose network connectivity to your Jetson entirely.

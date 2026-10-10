## Configuration NFS — PC Fedora Hôte (192.168.1.60)

Pour que le PV Hermes pointe vers `/var/data/hermes` sur le PC Fedora hôte,
le PC doit exposer ce répertoire via NFS.

### 1. Installer et démarrer NFS server

```bash
sudo dnf install -y nfs-utils
sudo systemctl enable --now nfs-server
```

### 2. Créer et exporter le répertoire

```bash
sudo mkdir -p /var/data/hermes
sudo chmod 0777 /var/data/hermes
sudo chown nfsnobody:nfsnobody /var/data/hermes

# Ajouter l'export NFS
echo '/var/data/hermes 192.168.1.62(rw,sync,no_subtree_check,no_root_squash)' | sudo tee -a /etc/exports

sudo exportfs -ra
```

### 3. Configurer le firewall

```bash
sudo firewall-cmd --add-service=nfs --permanent
sudo firewall-cmd --add-service=rpc-bind --permanent
sudo firewall-cmd --add-service=mountd --permanent
sudo firewall-cmd --reload
```

### 4. Tester depuis la VM okdsnoapps

```bash
# Depuis le poste Windows
oc debug node/okdsnoapps -- chroot /host bash -c "
showmount -e 192.168.1.60
mount -t nfs 192.168.1.60:/var/data/hermes /mnt -o nfsvers=4
ls -la /mnt
umount /mnt
"
```

> Si `showmount` n'est pas disponible, utiliser `mount` directement.

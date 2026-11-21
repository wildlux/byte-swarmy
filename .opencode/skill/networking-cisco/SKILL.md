---
name: networking-cisco
description: Skill per comandi e concetti Cisco IOS (routing, switching, VLAN, ACL, NAT, DHCP, OSPF/EIGRP, troubleshooting) derivati dai materiali CCNA. Usa quando l'utente chiede comandi Cisco IOS o configurazione rete.
---

# Networking Cisco — skill per comandi e concetti Cisco IOS (CCNA)

Flusso: **contesto → comando → verifica → salvataggio**.

## 1. Scopo

- Comandi Cisco IOS per router/switch (configurazione, routing, switching).
- Concetti CCNA: VLAN, trunk, STP, ACL, NAT, DHCP, OSPF, EIGRP, static routing.

## 2. Comandi base

```text
enable
configure terminal
hostname R1
interface GigabitEthernet0/0
 ip address 192.168.1.1 255.255.255.0
 no shutdown
exit
copy running-config startup-config
```

## 3. Routing

```text
# Statico
ip route 10.0.0.0 255.0.0.0 192.168.1.2
# Default
ip route 0.0.0.0 0.0.0.0 203.0.113.1
# OSPF
router ospf 1
 network 192.168.1.0 0.0.0.255 area 0
# EIGRP
router eigrp 100
 network 192.168.1.0 0.0.0.255
```

## 4. Switching / VLAN

```text
vlan 10
 name Sales
interface FastEthernet0/1
 switchport mode access
 switchport access vlan 10
interface GigabitEthernet0/1
 switchport mode trunk
 switchport trunk allowed vlan 10,20
```

## 5. ACL / NAT / DHCP

```text
# ACL standard
access-list 10 permit 192.168.1.0 0.0.0.255
# NAT overload
ip nat inside source list 1 interface GigabitEthernet0/1 overload
interface GigabitEthernet0/0
 ip nat inside
interface GigabitEthernet0/1
 ip nat outside
# DHCP
ip dhcp pool LAN
 network 192.168.1.0 255.255.255.0
 default-router 192.168.1.1
 dns-server 8.8.8.8
```

## 6. Verifica

```text
show ip interface brief
show ip route
show vlan brief
show interfaces trunk
show access-lists
show ip nat translations
```

## 7. Quality gates

- Mai `write erase` senza conferma.
- Sempre `copy running-config startup-config` dopo le modifiche.
- Documentare con `description` su ogni interfaccia.

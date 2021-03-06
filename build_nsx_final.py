#!/usr/bin/env python
# -*- coding: utf-8 -*-
#Import Libraries from PyNSXv and NSXRaml

import ConfigParser
import json
import argparse
import subprocess
import time
import requests
from pkg_resources import resource_filename
from argparse import RawTextHelpFormatter
from tabulate import tabulate
from nsxramlclient.client import NsxClient
from pynsxv.library.nsx_logical_switch import *
from pynsxv.library.nsx_dlr import *
from pynsxv.library.nsx_esg import *
from pynsxv.library.nsx_dfw import *
from pynsxv.library.nsx_lb import *
from pynsxv.library.libutils import *

#ignore cert warnings from NSX when making direct api calls
from requests.packages.urllib3.exceptions import InsecureRequestWarning
requests.packages.urllib3.disable_warnings(InsecureRequestWarning)

nsxraml_file = '/usr/local/lib/python2.7/dist-packages/pynsxv/library/api_spec/nsxvapi.raml'

# Script Variables
# NSX Manager 
nsx_manager = '192.168.110.15'
nsx_username = 'admin'
nsx_password = 'VMware1!'

#vCenter connection details
vcenter = '192.168.110.22'
vcenter_user = 'administrator@vsphere.local'
vcenter_passwd = 'VMware1!'
#Transport Zone to deploy to
transport_zone = 'Global_Transport_Zone'
# VC objects for edge/control VM deployment
datacenter_name = 'Datacenter Site A'
edge_datastore = 'ds-iscsi-01a'
edge_cluster = 'Management-Edge-Cluster'
#May update with a config file. Below is guid on reading config file.
#config = ConfigParser.ConfigParser()
#config.read("nsx.ini")
#nsxmanager = config.get('nsxv', 'nsx_manager')

#Environment Details

#Logical switches
new_ls_name1 = 'py-web01'
interface_ip_1 = "10.10.1.1"
interface_subnet_1 = "255.255.255.0"

new_ls_name2 = 'py-app01'
interface_ip_2 = "10.10.2.1"
interface_subnet_2 = "255.255.255.0"

new_ls_name3 = 'py-db01'
interface_ip_3 = "10.10.3.1"
interface_subnet_3 = "255.255.255.0"
new_tp_ls_name = 'py-transport01'

#DLR Details
dlr_name = 'py-dlr01'
dlr_pwd = 'VMware1!VMware1!'
dlr_size = 'Compact'
ha_ls_name = 'vds-mgt_VM Network'
uplink_ip = '172.16.2.2'
uplink_subnet = '255.255.255.248'
uplink_dgw = '172.16.2.1'

# ESG details
esg_name = 'py-esg01'
esg_un = 'admin'
esg_pwd = 'VMware1!VMware1!'
esg_size = 'Compact'
default_pg = 'vds-mgt_VM Network'
esg_remote_access = "True"

#ESG Interfaces
esg_ifindex_1 = "0"
esg_ipaddr_1 = "192.168.119.200"
esg_netmask_1 = "255.255.255.0"
dgw_ip = "192.168.119.1"
esg_vnic_type_1 = "uplink"
esg_ifindex_2 = "1"
esg_ipaddr_2 = "172.16.2.1"
esg_netmask_2 = "255.255.255.248"
esg_vnic_type_2 = "internal"

# Configure LB

lb_app_profile = "py-ap-http1"
lb_proto = "HTTP"
lb_pool_name = "py-pool-web"
lb_monitor = "default_tcp_monitor"
lb_vip_name = "py-vip-web"
lb_vip_ip = "192.168.119.201"
lb_vip_port = "80"

# Collect vCenter MoID https://<vcenterIP>/mob
vccontent = connect_to_vc(vcenter, vcenter_user, vcenter_passwd)
datacentermoid = get_datacentermoid(vccontent, datacenter_name)
datastoremoid = get_datastoremoid(vccontent, edge_datastore)
resourcepoolmoid = get_edgeresourcepoolmoid(vccontent, edge_cluster)
print "Connected to VC %s"%(vcenter)

# Connect to NSX manager
client_session = NsxClient(nsxraml_file, nsx_manager, nsx_username,nsx_password, debug=False)
print  "Connected to NSX manager %s"%(nsx_manager)


# Get MoID of for HA vds portgroup 
ha_ls_id = get_vdsportgroupid(vccontent, ha_ls_name)
# Get moid of uplink portgroup
default_pg_id = get_vdsportgroupid(vccontent, default_pg)

# Create the logical switches
logical_switch_create (client_session, transport_zone, new_ls_name1)
logical_switch_create (client_session, transport_zone, new_ls_name2)
logical_switch_create (client_session, transport_zone, new_ls_name3)
logical_switch_create (client_session, transport_zone, new_tp_ls_name)
print "Created logical switches %s, %s, %s and %s"%(new_ls_name1, new_ls_name2, new_ls_name3, new_tp_ls_name)

# Get ID of uplink logical switch Transport
uplink_ls_id,null = get_logical_switch(client_session, new_tp_ls_name)

# Create DLR
print "Deploying NSX DLR %s for some awesome distributed in kernel routing..."%(dlr_name)

dlr_create(client_session, dlr_name, dlr_pwd, dlr_size, datacentermoid, datastoremoid,
                resourcepoolmoid, ha_ls_id, uplink_ls_id, uplink_ip, uplink_subnet, uplink_dgw)

# Get DLR ID
dlr_id, null = dlr_read(client_session, dlr_name)

# Plum logical networks to DLR
interface_ls_id,null = get_logical_switch(client_session, new_ls_name1)
dlr_add_interface(client_session, dlr_id, interface_ls_id, interface_ip_1, interface_subnet_1)

interface_ls_id,null = get_logical_switch(client_session, new_ls_name2)
dlr_add_interface(client_session, dlr_id, interface_ls_id, interface_ip_2, interface_subnet_2)

interface_ls_id,null = get_logical_switch(client_session, new_ls_name3)
dlr_add_interface(client_session, dlr_id, interface_ls_id, interface_ip_3, interface_subnet_3)
print "Connected logical networks %s, %s, %s, %s to DLR and configured the gateway IP for all logical switches"%(new_ls_name1, new_ls_name2, new_ls_name3, new_tp_ls_name)

# Build an ESG
print "Building new Edge Services Gateway %s"%(esg_name)
esg_create(client_session, esg_name, esg_pwd, esg_size, datacentermoid, datastoremoid, resourcepoolmoid,
                        default_pg_id, esg_un, esg_remote_access)

# Configure ESG Uplink interface
esg_cfg_interface(client_session, esg_name, esg_ifindex_1, esg_ipaddr_1, esg_netmask_1, vnic_type=esg_vnic_type_1)

# Add Edge ineternal interface
interface_ls_id,null = get_logical_switch(client_session, new_tp_ls_name)
esg_cfg_interface(client_session, esg_name, esg_ifindex_2, esg_ipaddr_2, esg_netmask_2, is_connected='true', portgroup_id=interface_ls_id, vnic_type=esg_vnic_type_2)
print "Almost done... Thanks for being patient. Just connected the %s interface to the %s"%(new_tp_ls_name, esg_name)

# ESG Accept Rule
esg_fw_default_set(client_session, esg_name, "accept", logging_enabled=None)

## Enable LB Config
load_balancer(client_session, esg_name, enabled=True)

## Enable LB app profile
add_app_profile(client_session, esg_name, lb_app_profile, lb_proto)

## Create web Pool.
add_pool(client_session, esg_name, lb_pool_name, monitor=lb_monitor)
add_member(client_session, esg_name, lb_pool_name, "web01", "10.10.1.11", port="80")
add_member(client_session, esg_name, lb_pool_name, "web02", "10.10.1.12", port="80")

## Create the LB Web VIP and configure secondary EDG interface
esg_cfg_interface(client_session, esg_name, "0", "192.168.119.200", "255.255.255.0", secondary_ips=lb_vip_ip)
add_vip(client_session, esg_name, lb_vip_name, lb_app_profile, lb_vip_ip, lb_proto, lb_vip_port, lb_pool_name)

print "Configured Load Balancer vip %s, pool %s including 2 web svrs, profile %s on ESG %s "%(lb_vip_name, lb_pool_name, lb_app_profile, esg_name)

#Add CUstomer things as pynsxv does nto support ospf

#dlr_name = "py-dlr01"
#edgeId, null = dlr_read(client_session, dlr_name)
print "Adding OSPF Configuration to the %s Distributed logical router"%(dlr_name)

#initialize variables with needed info for input file and to make NSX REST API call
#nsx_username = "admin"
#nsx_password = "VMware1!"
nsx_url = "https://192.168.110.15/api/4.0/edges/{}/routing/config".format( dlr_id )
myheaders={'content-type':'application/xml'}

#create XML payload with ospf information for DLR
payload ='''

<routing>
    <enabled>true</enabled>
    <routingGlobalConfig>
      <routerId>172.16.2.2</routerId>
      <ecmp>false</ecmp>
      <logging>
        <enable>true</enable>
        <logLevel>info</logLevel>
      </logging>
    </routingGlobalConfig>
    <staticRouting>
      <defaultRoute>
       <vnic>2</vnic>
        <mtu>1500</mtu>
        <gatewayAddress>172.16.2.1</gatewayAddress>
      </defaultRoute>
      <staticRoutes/>
    </staticRouting>
    <ospf>
      <enabled>true</enabled>
      <protocolAddress>172.16.2.3</protocolAddress>
      <forwardingAddress>172.16.2.2</forwardingAddress>
      <ospfAreas>
        <ospfArea>
          <areaId>10</areaId>
          <type>normal</type>
          <authentication>
            <type>none</type>
          </authentication>
        </ospfArea>
      </ospfAreas>
      <ospfInterfaces>
        <ospfInterface>
          <vnic>2</vnic>
          <areaId>10</areaId>
          <helloInterval>10</helloInterval>
          <deadInterval>40</deadInterval>
          <priority>128</priority>
          <cost>1</cost>
          <mtuIgnore>true</mtuIgnore>
        </ospfInterface>
      </ospfInterfaces>
      <redistribution>
        <enabled>true</enabled>
        <rules>
          <rule>
            <id>0</id>
            <from>
              <isis>false</isis>
              <ospf>true</ospf>
              <bgp>false</bgp>
              <static>true</static>
              <connected>true</connected>
            </from>
            <action>permit</action>
          </rule>
        </rules>
      </redistribution>
      <gracefulRestart>true</gracefulRestart>
      <defaultOriginate>true</defaultOriginate>
    </ospf>
  </routing>'''


#print payload    #uncomment this for debugging - payload for REST API request call
#call NSX REST API to create Security Group with XML payload just created
try: response = requests.put(nsx_url, data=payload, headers=myheaders, auth=(nsx_username,nsx_password), verify=False)
except requests.exceptions.ConnectionError as e:
        print "Connection error!"

print response.text

# Do the same for the esg

esg_Id, null = esg_read(client_session, esg_name)

print "Adding OSPF Configuration to the %s Edge Services Gateway. Note, we had to use xml here as pynsxv is yet to support bgp or ospf config"%(esg_name)
#initialize variables with needed info for input file and to make NSX REST API call
#nsx_username = "admin"
#nsx_password = "VMware1!"
nsx_url = "https://192.168.110.15/api/4.0/edges/{}/routing/config".format( esg_Id )
myheaders={'content-type':'application/xml'}
router_id = esg_ipaddr_1

#create XML payload with ospf information for DLR
payload ='''

<routing>
    <enabled>true</enabled>
    <routingGlobalConfig>
      <routerId>192.168.119.200</routerId>
      <ecmp>false</ecmp>
      <logging>
        <enable>true</enable>
        <logLevel>info</logLevel>
      </logging>
    </routingGlobalConfig>
    <staticRouting>
      <defaultRoute>
        <mtu>1500</mtu>
        <gatewayAddress>192.168.119.1</gatewayAddress>
      </defaultRoute>
      <staticRoutes/>
    </staticRouting>
    <ospf>
      <enabled>true</enabled>
      <ospfAreas>
        <ospfArea>
          <areaId>10</areaId>
          <type>normal</type>
          <authentication>
            <type>none</type>
          </authentication>
        </ospfArea>
      </ospfAreas>
      <ospfInterfaces>
        <ospfInterface>
          <vnic>1</vnic>
          <areaId>10</areaId>
          <helloInterval>10</helloInterval>
          <deadInterval>40</deadInterval>
          <priority>128</priority>
          <cost>1</cost>
          <mtuIgnore>true</mtuIgnore>
        </ospfInterface>
      </ospfInterfaces>
      <redistribution>
        <enabled>true</enabled>
        <rules>
          <rule>
            <id>0</id>
            <from>
              <isis>false</isis>
              <ospf>true</ospf>
              <bgp>false</bgp>
              <static>true</static>
              <connected>true</connected>
            </from>
            <action>permit</action>
          </rule>
        </rules>
      </redistribution>
      <gracefulRestart>true</gracefulRestart>
      <defaultOriginate>true</defaultOriginate>
    </ospf>
  </routing>'''


#print payload    #uncomment this for debugging - payload for REST API request call
#call NSX REST API to create Security Group with XML payload just created
try: response = requests.put(nsx_url, data=payload, headers=myheaders, auth=(nsx_username,nsx_password), verify=False)
except requests.exceptions.ConnectionError as e:
        print "Connection error!"

print response.text


# Default route North
esg_dgw_set(client_session, esg_name, dgw_ip, "0")
print "Added default gateway for %s. He needs to know who his next hop is."%(esg_name)
print "Phew, now that that is done, let's check out what we built"


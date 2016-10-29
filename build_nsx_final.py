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

#Read nsx.ini
config = ConfigParser.ConfigParser()
config.read("nsx.ini")
nsxmanager = config.get('nsxv', 'nsx_manager')
nsx_username = config.get('nsxv', 'nsx_username')
nsx_password = config.get('nsxv', 'nsx_password')
vcenter = config.get('vcenter', 'vcenter')
vcenter_user = config.get('vcenter', 'vcenter_user')
vcenter_passwd = config.get('vcenter', 'vcenter_passwd')
transport_zone = config.get('defaults', 'transport_zone')
datacenter_name = config.get('defaults', 'datacenter_name')
edge_datastore = config.get('defaults', 'edge_datastore')
edge_cluster = config.get('defaults', 'edge_cluster')

# Check that im reading the dang file
#print nsx_username
#print datacenter_name
#print vcenter_user

# Collect vCenter MoID https://<vcenterIP>/mob
vccontent = connect_to_vc(vcenter, vcenter_user, vcenter_passwd)
datacentermoid = get_datacentermoid(vccontent, datacenter_name)
datastoremoid = get_datastoremoid(vccontent, edge_datastore)
resourcepoolmoid = get_edgeresourcepoolmoid(vccontent, edge_cluster)
print "Connected to VC %s"%(vcenter)

# Connect to NSX manager
client_session = NsxClient(nsxraml_file, nsxmanager, nsx_username,nsx_password, debug=False)
print  "Connected to NSX manager %s"%(nsxmanager)

# Create the logical switches
new_ls_name1 = 'py-web01'
logical_switch_create (client_session, transport_zone, new_ls_name1)
new_ls_name2 = 'py-app01'
logical_switch_create (client_session, transport_zone, new_ls_name2)
new_ls_name3 = 'py-db01'
logical_switch_create (client_session, transport_zone, new_ls_name3)
new_tp_ls_name = 'py-transport01'
logical_switch_create (client_session, transport_zone, new_tp_ls_name)
print "Created logical switches %s, %s, %s and %s"%(new_ls_name1, new_ls_name2, new_ls_name3, new_tp_ls_name)

# Create DLR

dlr_name = 'py-dlr01'
dlr_pwd = 'VMware1!VMware1!'
dlr_size = 'Compact'
ha_ls_name = 'vds-mgt_VM Network'
uplink_ls_name = new_tp_ls_name
uplink_ip = '172.16.2.2'
uplink_subnet = '255.255.255.248'
uplink_dgw = '172.16.2.1'

# Get MoID of uplink logical switch.
ha_ls_id = get_vdsportgroupid(vccontent, ha_ls_name)
uplink_ls_id,null = get_logical_switch(client_session, uplink_ls_name)

#print ha_ls_id
#print uplink_ls_id

# Create DLR
print "Deploying NSX DLR %s for some awesome distributed in kernel routing... Quite efficiently I might add..."%(dlr_name)

dlr_create(client_session, dlr_name, dlr_pwd, dlr_size, datacentermoid, datastoremoid,
                resourcepoolmoid, ha_ls_id, uplink_ls_id, uplink_ip, uplink_subnet, uplink_dgw)

# Plum logical networks to DLR
interface_ls_name = new_ls_name1
interface_ip = "10.10.1.1"
interface_subnet = "255.255.255.0"
dlr_id, null = dlr_read(client_session, dlr_name)
interface_ls_id,null = get_logical_switch(client_session, interface_ls_name)
dlr_add_interface(client_session, dlr_id, interface_ls_id, interface_ip, interface_subnet)

interface_ls_name = new_ls_name2
interface_ip = "10.10.2.1"
interface_subnet = "255.255.255.0"
dlr_id, null = dlr_read(client_session, dlr_name)
interface_ls_id,null = get_logical_switch(client_session, interface_ls_name)
dlr_add_interface(client_session, dlr_id, interface_ls_id, interface_ip, interface_subnet)

interface_ls_name = new_ls_name3
interface_ip = "10.10.3.1"
interface_subnet = "255.255.255.0"
dlr_id, null = dlr_read(client_session, dlr_name)
interface_ls_id,null = get_logical_switch(client_session, interface_ls_name)
dlr_add_interface(client_session, dlr_id, interface_ls_id, interface_ip, interface_subnet)
print "Connected logical networks %s, %s, %s, %s to DLR and configured the gateway IP for all logical switches"%(new_ls_name1, new_ls_name2, new_ls_name3, new_tp_ls_name)

# ESG details
esg_name = 'py-esg01'
esg_un = 'admin'
esg_pwd = 'VMware1!VMware1!'
esg_size = 'Compact'
default_pg = 'vds-mgt_VM Network'
uplink_ls_name = new_tp_ls_name
esg_remote_access = "True"

# Get moid of uplink portgroup
default_pg_id = get_vdsportgroupid(vccontent, default_pg)

# Build an ESG
print "Building new Edge Services Gateway %s Live on stage. Pew Pew Pew"%(esg_name)
esg_create(client_session, esg_name, esg_pwd, esg_size, datacentermoid, datastoremoid, resourcepoolmoid,
                        default_pg_id, esg_un, esg_remote_access)

# Configure ESG Uplink interface
ifindex = "0"
ipaddr = "192.168.119.200"
netmask = "255.255.255.0"
vnic_type = "uplink"
esg_cfg_interface(client_session, esg_name, ifindex, ipaddr, netmask, vnic_type=vnic_type)

# Add Edge ineternal interface
ifindex = "1"
ipaddr = "172.16.2.1"
netmask = "255.255.255.248"
vnic_type = "internal"
interface_ls_name = new_tp_ls_name
interface_ls_id,null = get_logical_switch(client_session, interface_ls_name)
esg_cfg_interface(client_session, esg_name, ifindex, ipaddr, netmask, is_connected='true', portgroup_id=interface_ls_id, vnic_type=vnic_type)
print "Almost done... Thanks for being patient. Just connected the %s interface to the %s"%(interface_ls_name, esg_name)

# ESG Accept Rule
esg_fw_default_set(client_session, esg_name, "accept", logging_enabled=None)

#Add CUstomer things as pynsxv does nto support ospf

dlr_name = "py-dlr01"
edgeId, null = dlr_read(client_session, dlr_name)
print "Adding OSPF Configuration to the %s Distributed logical router"%(dlr_name)

#initialize variables with needed info for input file and to make NSX REST API call
#nsx_username = "admin"
#nsx_password = "VMware1!"
nsx_url = "https://192.168.110.15/api/4.0/edges/{}/routing/config".format( edgeId )
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


esg_name = "py-esg01"
edgeId, null = esg_read(client_session, esg_name)

print "Adding OSPF Configuration to the %s Edge Services Gateway. Note, we had to use xml here as pynsxv is yet to support bgp or ospf config"%(esg_name)
#initialize variables with needed info for input file and to make NSX REST API call
#nsx_username = "admin"
#nsx_password = "VMware1!"
nsx_url = "https://192.168.110.15/api/4.0/edges/{}/routing/config".format( edgeId )
myheaders={'content-type':'application/xml'}

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
dgw_ip = "192.168.119.1"
esg_dgw_set(client_session, esg_name, dgw_ip, "0")
print "Added default gateway for %s. He needs to know who his next hop is."%(esg_name)

# Default route
#subnet = "10.10.0.0/16"
#next_hop = "172.16.2.2"
#esg_route_add(client_session, esg_name, subnet, next_hop, "1")
#print "Adding static route from %s to %s as BGP is not supported in pynsxv as of yet :("%(esg_name, dlr_name)
print "Phew, now that that is done, let's check out what we built"
time.sleep(8)

# Execute some pynsxv commands to show the outputs of the build

p = subprocess.Popen(["pynsxv", "lswitch", "list"], stdout=subprocess.PIPE)
(output, err) = p.communicate()
print "*** List all Logical Switches***\n", output

time.sleep(4)
p = subprocess.Popen(["pynsxv", "dlr", "list"], stdout=subprocess.PIPE)
(output, err) = p.communicate()
print "*** List all Distributed Logical Routers***\n", output

time.sleep(4)
p = subprocess.Popen(["pynsxv", "dlr", "list_interfaces", "-n" "py-dlr01"], stdout=subprocess.PIPE)
(output, err) = p.communicate()
print "*** List Our DLR's interfaces ***\n", output

time.sleep(4)
p = subprocess.Popen(["pynsxv", "esg", "list"], stdout=subprocess.PIPE)
(output, err) = p.communicate()
print "*** List all ESG's ***\n", output

time.sleep(4)
p = subprocess.Popen(["pynsxv", "esg", "list_interfaces", "-n" "py-esg01"], stdout=subprocess.PIPE)
(output, err) = p.communicate()
print "*** List Our ESG's interfaces ***\n", output

#time.sleep(4)
#p = subprocess.Popen(["pynsxv", "esg", "list_routes", "-n" "py-esg01"], stdout=subprocess.PIPE)
#(output, err) = p.communicate()
#print "*** List Our ESG's statis routes ***\n", output
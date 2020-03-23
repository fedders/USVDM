# Purpose:     Correct input models for merging
#
# Author:      kristjan.vilgo
#
# Created:     26.02.2019
# Copyright:   (c) kristjan.vilgo 2019
# Licence:     GPLv2
#-------------------------------------------------------------------------------
import sys
sys.path.append("..")
import RDF_parser
import CGMES_tools
import pandas
from uuid import uuid4

import json

#input_data = r"C:\Users\kristjan.vilgo\Downloads\20200115T0930Z_1D_RTEFRANCE_EQ_001.zip"
#input_data = r"C:\Users\kristjan.vilgo\Downloads\input_data.zip"
input_data = r"C:\Users\kristjan.vilgo\Downloads\Input_IGMs.zip"
boundary = r"C:\Users\kristjan.vilgo\Downloads\20200129T0000Z_ENTSO-E_BD_1164.zip"

xnode_conf = r"C:\USVDM\Tools\RDF_PARSER\examples\xnodes_for_tieflows.xlsx"

# Read data
data = pandas.read_RDF([input_data, boundary])

# Parse metadata to file header
data = CGMES_tools.update_FullModel_from_filename(data)

### Fix EnergyConsumers ###

# Fix all EnergyConsumers to ConformLoads
loads = data.query("KEY == 'Type' & VALUE == 'EnergyConsumer'")
loads.VALUE = "ConformLoad"
data.update(loads)

#import tieflow

#initial_flow = tieflow.get_EquivalentInjections_NetInterchange_TieFlows(data)


### Fix Tieflows ###

# Get all EQ instances
eq_instances = data.query("KEY == 'Model.profile' & VALUE == 'http://entsoe.eu/CIM/EquipmentCore/3/1'")

# Get all ControlAreas in EQ instances
control_areas = data.query("KEY == 'Type' & VALUE == 'ControlArea'").merge(eq_instances["INSTANCE_ID"], on="INSTANCE_ID")

# Get all existing TieFlows
tieflows = data.query("KEY == 'Type' & VALUE == 'TieFlow'")

# Get all xnodes participating in AC NP
ac_xnodes = pandas.read_excel(xnode_conf).query("TieFlow == True")
print("AC TieFlow Terminals form conf = {}".format(len(ac_xnodes)))

# Remove all existing TieFlows
data = data.drop(data.reset_index().merge(tieflows["ID"], on="ID")["index"])

# Create new TieFlow data
"""ID = uuid4, TieFlow.ControlArea, TieFlow.Terminal, TieFlow.positiveFlowIn = true, Type = TieFlow"""

# Find instance ID where Terminal belongs to
new_tieflows = data.merge(ac_xnodes["ID_Terminal"], left_on="ID", right_on="ID_Terminal").drop_duplicates("ID")

# data.merge(ac_xnodes["ID_Terminal"], left_on="ID", right_on="ID_Terminal", how="outer", indicator=True).query("_merge == 'right_only'")["ID_Terminal"] #DEBUG

# Map TieFlows to ControlAreas via INSTANCE_ID
new_tieflows = new_tieflows.merge(control_areas, on="INSTANCE_ID", suffixes=("", "_ControlArea"))

# CleanUp - keep only needed columns and add missing values
new_tieflows = new_tieflows[["INSTANCE_ID", "ID_Terminal", "ID_ControlArea"]].rename(columns={"ID_Terminal": "TieFlow.Terminal",
                                                                                              "ID_ControlArea": "TieFlow.ControlArea"})

new_tieflows["TieFlow.positiveFlowIn"] = "true"
new_tieflows["Type"] = "TieFlow"

# Add TieFlow ID-s
new_tieflows["ID"] = new_tieflows.apply(lambda x: str(uuid4()), axis=1)
new_tieflows = new_tieflows.set_index("ID")

# Convert to triplet
new_tieflows_triplet = RDF_parser.tableview_to_triplet(new_tieflows[['TieFlow.Terminal', 'TieFlow.ControlArea', 'TieFlow.positiveFlowIn', 'Type']])

# Add INSTANCE_ID to triplet
new_tieflows_triplet = new_tieflows_triplet.merge(new_tieflows.reset_index()[["ID", "INSTANCE_ID"]], on="ID")

# Add to data
data = data.append(new_tieflows_triplet, ignore_index=True)

#final_flow = tieflow.get_EquivalentInjections_NetInterchange_TieFlows(data)


## EXPORT ###

# Set namepsaces for export

namespace_map = dict(    cim="http://iec.ch/TC57/2013/CIM-schema-cim16#",
                         cims="http://iec.ch/TC57/1999/rdf-schema-extensions-19990926#",
                         entsoe="http://entsoe.eu/CIM/SchemaExtension/3/1#",
                         cgmbp="http://entsoe.eu/CIM/Extensions/CGM-BP/2020#",
                         md="http://iec.ch/TC57/61970-552/ModelDescription/1#",
                         rdf="http://www.w3.org/1999/02/22-rdf-syntax-ns#",
                         rdfs="http://www.w3.org/2000/01/rdf-schema#",
                         xsd="http://www.w3.org/2001/XMLSchema#")

export_undefined = False
export_type      = "xml_per_instance_zip_per_all"

# Load export format configuration
with open(r"C:\USVDM\Tools\RDF_PARSER\entsoe_v2.4.15_2014-08-07.json", "r") as conf_file:
    rdf_map = json.load(conf_file)

# Export triplet to CGMES
data.export_to_cimxml(rdf_map=rdf_map,
                      namespace_map=namespace_map,
                      export_undefined=export_undefined,
                      export_type=export_type)


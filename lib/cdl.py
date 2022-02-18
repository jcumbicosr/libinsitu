import sys
from typing import Dict

from lib.common import parse_value
from lib.log import info, obj2json, warning, debug
import re

class Variable :
    def __init__(self, name, type, dimensions):
        self.type = type
        self.dimensions = dimensions
        self.name = name
        self.attributes = {}

class CDL :
    def __init__(self):
        self.dimensions : Dict[str, int] = {}
        self.variables : Dict[str, Variable] = {}
        self.global_attributes = {}

def replace_placeholders(strval, attributes) :

    def repl(m) :
        key = m.group().strip("{").strip("}")

        if not key in attributes :
            warning("Key : '%s' not found in attributes, using empty string instead" % key)
            return ""

        res = attributes[key]
        return "" if res is None else str(res)

    return re.sub(r'{\w+}', repl, strval)

def parse_cdl(lines, attributes) :

    res = CDL()

    section = None

    """ Parse CDL file """
    for line in lines :
        line = line.strip()

        # Skip comments
        if line.startswith("//") or len(line) == 0:
            continue

        # key = value
        if "=" in line :
            line = line.strip(";")
            key, val = line.split("=")
            key = key.strip()
            val = parse_value(val.strip())

            if section == "dimensions" :

                # Defining dimension
                dim = 0 if val == "UNLIMITED" else int(val)
                res.dimensions[key] = dim

            elif section == "variables" :
                varname, attrname = key.split(":")
                if isinstance(val, str) :
                    val = replace_placeholders(val, attributes)
                if varname == "" :
                    res.global_attributes[attrname] = val
                else :
                    res.variables[varname].attributes[attrname] = val
            else :
                raise Exception("Assignement outside any section : %s" % line)


        # Skip start or end
        elif "{" in line or "}" in line :
            continue

        # Change section
        elif ":" in line :
            section = line.strip(":").strip()
            continue

        elif ";" in line :
            # New var
            line = line.strip(";").strip()
            type, var = line.split()

            if type == "char" :
                type ="c"
            elif type == "float" :
                type="f4"
            elif type == "int" :
                type="i4"
            elif type == "uint":
                type = "u4"

            dims=[]
            if "(" in var :
                var, dims = var.split("(")
                dims = dims.strip(")").strip().split(",")
            res.variables[var] = Variable(var, type, dims)
        else :
            raise Exception("Bad line : %s" %line)

    return res



def cdl2netcdf(ncfile, cdl: CDL) :
    """Init NetCDF file from a CDL"""

    for dimname, dim in cdl.dimensions.items() :

        # Already there, skipping
        if dimname in ncfile.dimensions :
            continue

        info("Adding dimension '%s'", dimname)
        ncfile.createDimension(dimname, dim)

    for varname, vardef in cdl.variables.items() :

        # Already there, skipping
        if varname in ncfile.variables:
            continue

        info("Adding variable '%s'", varname)
        var = ncfile.createVariable(varname, vardef.type, vardef.dimensions, zlib=True)

        # Set attributes
        for key, val in vardef.attributes.items():
            var.setncattr(key, val)

    # Global attributes
    for key, val in cdl.global_attributes.items():
        ncfile.setncattr(key, val)




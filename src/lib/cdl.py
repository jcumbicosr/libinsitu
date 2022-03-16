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

def update_attributes(dest, src, dry_run=False, delete=False) :

    dry_prefix = "would " if dry_run else ""

    existing_attrs = set(dest.ncattrs())
    new_attrs = set(src.keys())

    extra_attrs = existing_attrs - new_attrs

    if delete :
        for attrname in extra_attrs :
            info(dry_prefix + "delete attribute %s#%s" % (dest.name, attrname))
            if not dry_run :
                dest.delncattr(attrname)

    for key, val in src.items() :
        oldval = None if not key in existing_attrs else dest.getncattr(key)
        if oldval != val :

            if (val is None or val == "") and not delete :
                continue

            if oldval is not None :
                info(dry_prefix + "update attribute %s#%s %s -> %s" % (dest.name, key, oldval, val))

            if not dry_run:
                dest.setncattr(key, val)


def cdl2netcdf(ncfile, cdl: CDL, dry_run=False, delete_attrs=False) :
    """Init NetCDF file from a CDL"""

    for dimname, dim in cdl.dimensions.items() :

        # Already there, skipping
        if not dimname in ncfile.dimensions and not dry_run :
            info("Adding dimension '%s'", dimname)
            ncfile.createDimension(dimname, dim)

    for varname, vardef in cdl.variables.items() :

        # Already there, skipping
        if not varname in ncfile.variables and not dry_run:
            info("Adding variable '%s'", varname)
            ncfile.createVariable(varname, vardef.type, vardef.dimensions, zlib=True)

        var = ncfile.variables[varname]

        # Update attributes
        update_attributes(var, vardef.attributes, dry_run, delete_attrs)

    # Update global attributes
    update_attributes(ncfile, cdl.global_attributes, dry_run, delete_attrs)




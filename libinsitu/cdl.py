import re
from copy import deepcopy
from typing import Dict
from libinsitu import STATION_NAME_VAR
from libinsitu.common import parse_value, DATA_VARS, read_res, CDL_PATH, LONGITUDE_VAR, LATITUDE_VAR, ELEVATION_VAR, \
    fill_str, TIME_VAR
from libinsitu.log import info, warning


SYSTEM_ATTRIBUTES = ["_FillValue"]

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

def parse_cdl(lines, attributes=dict()) :
    """ Parse CDL file """

    res = CDL()

    section = None
    curr_var = None

    for line in lines :
        line = line.strip()

        # Skip comments
        if line.startswith("#") or len(line) == 0:
            continue

        if "#" in line :
            line = line.split("#")[0]
            line = line.strip()

        # key = value
        if "=" in line :
            line = line.strip(";")
            key, val = line.split("=", 1)
            key = key.strip()
            val = parse_value(val.strip(), split=True)

            if isinstance(val, str):
                val = replace_placeholders(val.strip(), attributes)

            # Defining dimension
            if section == "dimensions" :

                dim = 0 if val == "UNLIMITED" else int(val)
                res.dimensions[key] = dim

            elif section == "variables" :
                varname, attrname = key.split(":")

                if varname == "*" :
                    varname = curr_var

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
            elif type == "string" :
                type = str
            elif type == "float" :
                type="f4"
            elif type == "int" :
                type="i4"
            elif type == "short":
                type = "i2"
            elif type == "uint":
                type = "u4"

            dims=[]
            if "(" in var :
                var, dims = var.split("(")
                dims = dims.strip(")").strip().split(",")
            res.variables[var] = Variable(var, type, dims)
            curr_var = var
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

        if key in SYSTEM_ATTRIBUTES :
            # Do not update system attributes
            continue

        if oldval != val :

            if (val is None or val == "") and not delete :
                continue

            info(dry_prefix + "update attribute %s#%s %s -> %s" % (dest.name, key, oldval, val))

            if not dry_run:
                dest.setncattr(key, val)


def cmp_var(var,  vardef:Variable) :
    return var.dtype == vardef.type and var.dimensions == tuple(vardef.dimensions)

def create_or_replace_var(ncfile, vardef:Variable, dry_run=False) :

    if vardef.name in ncfile.variables:

        var = ncfile.variables[vardef.name]

        if cmp_var(var, vardef):
            # Same var -> skipping
            return

        # Different vars
        if dry_run:
            info("Would replace var : %s" % vardef.name)
        else:
            info("Replacing var : %s" % vardef.name)
            del ncfile.variables[vardef.name]

    if dry_run :
        info("Would add variable : %s" % vardef.name)
        return

    least_significant_digit = vardef.attributes.get("least_significant_digit", None)
    fill_value = vardef.attributes.get("_FillValue", None)

    info("Adding variable '%s'. Precision:%s" %  (vardef.name, least_significant_digit))

    ncfile.createVariable(
        vardef.name, vardef.type, vardef.dimensions,
        zlib=vardef.type is not str,
        complevel=9,
        least_significant_digit=least_significant_digit,
        fill_value=fill_value)

def initVar(ncfile, vardef:Variable, dry_run=False, delete_attrs=False) :

    create_or_replace_var(ncfile, vardef, dry_run)

    var = ncfile.variables[vardef.name]

    # Update attributes
    update_attributes(var, vardef.attributes, dry_run, delete_attrs)

def cdl2netcdf(ncfile, cdl: CDL, dry_run=False, delete_attrs=False) :
    """Init NetCDF file from a CDL"""

    for dimname, dim in cdl.dimensions.items() :

        # Already there, skipping
        if not dimname in ncfile.dimensions and not dry_run :
            info("Adding dimension '%s'", dimname)
            ncfile.createDimension(dimname, dim)

    for varname, vardef in cdl.variables.items() :
        initVar(ncfile, vardef, dry_run, delete_attrs)

    # Update global attributes
    update_attributes(ncfile, cdl.global_attributes, dry_run, delete_attrs)


def init_nc(netcdf, properties, data_vars=DATA_VARS, dry_run=False, delete_attrs=False) :

    try:
        # Try to load custom CDL first
        custom_name = properties["Network_ID"] + ".cdl"
        cdl = parse_cdl(read_res(custom_name), properties)
        info("Used custom CDL : %s" % custom_name)

    except FileNotFoundError:
        cdl = parse_cdl(read_res(CDL_PATH), properties)

    # Ensures all requested data vars are defined
    missing_vars = set(data_var for data_var in data_vars if data_var not in cdl.variables)
    if len(missing_vars) > 0 :
        raise Exception("Unknown data vars : %s" % missing_vars)

    filtered_cdl = deepcopy(cdl)

    # Filter data vars (variables with "time" dimension)
    # Also adds the "Time" variable
    filtered_cdl.variables = dict()
    for key, var in cdl.variables.items() :
        if "time" in var.dimensions and not key in data_vars + [TIME_VAR] :
            continue
        filtered_cdl.variables[key] = var

    cdl2netcdf(netcdf, filtered_cdl, dry_run, delete_attrs)

    if not dry_run :

        # Init scalar vars
        netcdf.variables[LONGITUDE_VAR][0] = properties["Station_Longitude"]
        netcdf.variables[LATITUDE_VAR][0] = properties["Station_Latitude"]
        netcdf.variables[ELEVATION_VAR][0] = properties["Station_Elevation"]

        fill_str(netcdf, STATION_NAME_VAR, properties["Station_ID"])

    return cdl





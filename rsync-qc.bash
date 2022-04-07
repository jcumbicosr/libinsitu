#!/usr/bin/bash
rsync -rtL --delete --chown=tds-insitu:tomcat out/qc/enerMENA/ tds-insitu@brume:/home/thredds_content/thredds/public/enermenastations/qc
rsync -rtL --delete --chown=tds-insitu:tomcat out/qc/ABOM/ tds-insitu@brume:/home/thredds_content/thredds/public/bomstations/qc
rsync -rtL --delete --chown=tds-insitu:tomcat out/qc/BSRN/ tds-insitu@brume:/home/thredds_content/thredds/public/bsrnstations/qc


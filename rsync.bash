
rsync -rt --delete --chmod=644 --chown=tds-insitu:tomcat out/enerMENA/ tds-insitu@brume:/home/thredds_content/thredds/public/enermenastations/
rsync -rt --delete --chmod=644 --chown=tds-insitu:tomcat out/ABOM/ tds-insitu@brume:/home/thredds_content/thredds/public/bomstations/
rsync -rt --delete --chmod=644 --chown=tds-insitu:tomcat out/BSRN/ tds-insitu@brume:/home/thredds_content/thredds/public/bsrnstations/


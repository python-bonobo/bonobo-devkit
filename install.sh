VENDORS="edgy-event edgy-project"

for vendor in $VENDORS; do
  (cd vendors/$vendor; pip install -e .)
done

(cd bonobo; make install-dev)


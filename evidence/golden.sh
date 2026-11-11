#!/bin/bash
# Runs a fixed CLI script against a fresh state file; prints stdout, stderr and exit code.
D=$(mktemp -d); S=$D/state.json
run(){ echo "\$ $*"; python -m supplydesk --data $S "$@" 2>&1; echo "exit=$?"; }
run catalog
run quote --customer student --fulfillment delivery --item hoodie:2
run quote --customer student --item notebook:10
run quote --item notebook:0
run quote --item ghost:1
run place --item mug:1 --item pen-pack:3
run place --customer student --fulfillment delivery --item bag:4
run place --item notebook:3 --item notebook:3
run orders
run cancel ORD-0001
run cancel ORD-0001
run cancel ORD-0099
run show ORD-0002
run catalog
printf '3\nstudent\nhoodie\n2\n\ndelivery\ny\n4\n6\nORD-0001\nn\n0\n' | python -m supplydesk --data $S; echo "exit=$?"
rm -rf $D

#!/usr/bin/env bash

echo "=== Testing Container ID Detection ==="
echo ""

echo "1. Current VMs (qm list):"
qm list
echo ""

echo "2. Current containers (pct list):"
pct list
echo ""

echo "3. All used IDs (both VMs and containers):"
echo "   From qm:"
qm list | awk 'NR>1 {print $1}'
echo "   From pct:"
pct list | awk 'NR>1 {print $1}'
echo ""

echo "4. Testing get_next_free_ctid function (checking BOTH VMs and containers):"
get_next_free_ctid() {
    local ctid=100
    echo "   Starting search from ID: $ctid"
    while true; do
        # Check if ID exists in VMs (qm list)
        if qm list | awk 'NR>1 {print $1}' | grep -q "^${ctid}$"; then
            echo "   ID $ctid is TAKEN by VM, checking next..."
            ctid=$((ctid + 1))
            continue
        fi
        # Check if ID exists in containers (pct list)
        if pct list | awk 'NR>1 {print $1}' | grep -q "^${ctid}$"; then
            echo "   ID $ctid is TAKEN by container, checking next..."
            ctid=$((ctid + 1))
            continue
        fi
        # ID is free!
        echo "   ID $ctid is FREE!"
        echo "$ctid"
        break
    done
}

NEXT_FREE=$(get_next_free_ctid)
echo ""
echo "5. RESULT: Next free ID is: $NEXT_FREE"
echo ""

echo "6. Verification - checking if ID $NEXT_FREE exists:"
if qm status "$NEXT_FREE" &>/dev/null 2>&1; then
    echo "   ERROR: ID $NEXT_FREE exists as VM!"
elif pct status "$NEXT_FREE" &>/dev/null 2>&1; then
    echo "   ERROR: ID $NEXT_FREE exists as container!"
else
    echo "   OK: ID $NEXT_FREE is truly free"
fi

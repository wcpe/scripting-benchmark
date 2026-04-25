var sum = 0
for (i in 0 until __ITER__) {
    sum += (lookupMap.get("k${i % 128}") as Int)
}
sum

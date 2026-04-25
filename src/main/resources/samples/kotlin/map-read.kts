var sum = 0
for (i in 0 until __ITER__) {
    sum += lookupMap["k${i % 128}"] ?: 0
}
sum

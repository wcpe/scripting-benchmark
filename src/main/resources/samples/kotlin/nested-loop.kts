var total = 0L
for (i in 0 until __ITER__) {
    for (j in 0 until 64) {
        total += (i * j) % 7
    }
}
total

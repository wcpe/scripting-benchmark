var total = 0
for (i in 0 until __ITER__) {
    val pos = message.indexOf(marker)
    val slice = message.substring(pos, pos + marker.length)
    total += pos + slice.length
}
total

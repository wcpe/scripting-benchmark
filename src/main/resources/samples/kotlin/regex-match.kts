var hits = 0
for (i in 0 until __ITER__) {
    val matcher = pattern.matcher(regexText)
    if (matcher.find()) {
        hits += matcher.group(1).length + matcher.group(2).length
    }
}
hits

var hits = 0;
for (var i = 0; i < __ITER__; i++) {
    var matcher = pattern.matcher(regexText);
    if (matcher.find()) {
        hits += matcher.group(1).length() + matcher.group(2).length();
    }
}
hits;

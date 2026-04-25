var total = 0;
for (var i = 0; i < __ITER__; i++) {
    var pos = message.indexOf(marker);
    var slice = message.substring(pos, pos + marker.length());
    total += pos + slice.length();
}
total;

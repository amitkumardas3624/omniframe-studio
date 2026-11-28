// === BOOTSTRAP ===
(function () {
    var v = window.__OMNIFRAME_COMPOSITION__.variables;
    var ids = ["boost", "your", "business", "withWord", "tag", "tagVertical", "lead",
        "lead2", "withYellow", "disc", "ring", "centre", "centre1", "centre2", "centre3",
        "wash", "tick", "intro", "stack", "stackTop", "stackWhite", "stackSub",
        "stackBlack",
        "badge", "badgeText", "contact", "contactChip", "phones", "site", "handles",
        "endCard", "glow"];
    var nodes = {};
    for (var i = 0; i < ids.length; i += 1) {
        nodes[ids[i]] = document.getElementById(ids[i]);
    }
    var base = {
        tagVertical: "rotate(-90deg)",
        withYellow: "rotate(-90deg)",
    };
    window.__A__ = { v: v, nodes: nodes, base: base };
})();

// === FRAME ===
(function () {
    var a = window.__A__;
    var nodes = a.nodes;
    var base = a.base;

    function clamp(x) { return x < 0 ? 0 : (x > 1 ? 1 : x); }
    function seg(t, from, to) { return clamp((t - from) / (to - from), 0, 1); }
    function easeInOut(p) {
        return p < 0.5 ? 2 * p * p : 1 - Math.pow(-2 * p + 2, 2) / 2;
    }
    function outExpo(p) { return p >= 1 ? 1 : 1 - Math.pow(2, -10 * p); }
    function outBack(p) {
        var c1 = 1.70158;
        var c3 = c1 + 1;
        return 1 + c3 * Math.pow(p - 1, 3) + c1 * Math.pow(p - 1, 2);
    }

    function set(id, opacity, transform) {
        var node = nodes[id];
        if (!node) return;
        node.style.opacity = String(clamp(opacity, 0, 1));
        node.style.visibility = opacity > 0.002 ? "visible" : "hidden";
        var extra = base[id] ? base[id] + " " : "";
        node.style.transform = extra + (transform || "");
    }

    function clear() {
        for (var key in nodes) {
            if (Object.prototype.hasOwnProperty.call(nodes, key)) set(key, 0, "");
        }
    }
    function set(id, opacity, transform, blur) {
        var node = nodes[id];
        if (!node) return;
        node.style.opacity = String(clamp(opacity, 0, 1));
        node.style.visibility = opacity > 0.002 ? "visible" : "hidden";
        var extra = base[id] ? base[id] + " " : "";
        node.style.transform = extra + (transform || "");
        var amount = blur || 0;
        node.style.filter = amount > 0.05 ? "blur(" + amount.toFixed(2) + "px)" : "";
    }

    window.seek = function (t) {
        clear();
        set("glow", 1, "");

        var boostIn = seg(t, 0.0, 0.55);
        var yourIn = seg(t, 0.5, 0.95);
        var businessIn = seg(t, 0.9, 1.35);
        var stackOut = seg(t, 1.8, 2.2);
        var hold = (1 - easeInOut(stackOut));
        set("boost", easeInOut(boostIn) * hold,
            "translateY(" + ((1 - easeInOut(boostIn)) * -26) + "px)",
            7 * (1 - easeInOut(boostIn)));
        set("your", easeInOut(yourIn) * hold,
            "translateY(" + ((1 - easeInOut(yourIn)) * -54) + "px)",
            8 * (1 - easeInOut(yourIn)));
        set("business", easeInOut(businessIn) * hold,
            "translateY(" + ((1 - easeInOut(businessIn)) * -54) + "px)",
            9 * (1 - easeInOut(businessIn)));

        var withIn = seg(t, 2.0, 2.55);
        var withOut = seg(t, 3.0, 3.5);
        set("withWord", easeInOut(withIn) * (1 - easeInOut(withOut)),
            "translateX(" + (easeInOut(withOut) * -430) + "px) scale("
            + (0.9 + 0.1 * easeInOut(withIn)) + ")",
            5 * (1 - easeInOut(withIn)));
        var tagIn = seg(t, 2.5, 2.95);
        set("tag", easeInOut(tagIn) * (1 - easeInOut(withOut)),
            "translateX(" + (easeInOut(withOut) * -430) + "px)",
            4 * (1 - easeInOut(tagIn)));

        var leadIn = seg(t, 3.45, 4.05);
        var leadOut = seg(t, 5.0, 5.4);
        var leadAlpha = easeInOut(leadIn) * (1 - easeInOut(leadOut));
        set("tagVertical", leadAlpha,
            "translateX(" + ((1 - easeInOut(leadIn)) * -70) + "px)");
        set("lead", leadAlpha,
            "translateY(" + ((1 - easeInOut(leadIn)) * -26) + "px)");
        set("lead2", leadAlpha,
            "translateY(" + ((1 - easeInOut(leadIn)) * -26) + "px)");
        var withY = seg(t, 3.7, 4.2);
        set("withYellow", easeInOut(withY) * (1 - easeInOut(leadOut)),
            "translateX(" + ((1 - easeInOut(withY)) * -70) + "px)");
        var discIn = seg(t, 4.7, 5.3);
        set("disc", easeInOut(discIn) * (1 - easeInOut(seg(t, 5.3, 5.6))),
            "scale(" + (0.2 + 0.8 * outBack(discIn)) + ")");

        var ringIn = seg(t, 5.4, 5.95);
        set("ring", easeInOut(ringIn) * (1 - easeInOut(seg(t, 7.5, 7.7))),
            "scale(" + (1.32 - 0.32 * easeInOut(ringIn)) + ")");
        var centreIn = seg(t, 5.95, 6.45);
        var swap = seg(t, 6.9, 7.35);
        set("centre", easeInOut(centreIn), "");
        set("centre1", easeInOut(centreIn) * (1 - easeInOut(swap)), "");
        set("centre2", easeInOut(centreIn) * (1 - easeInOut(seg(t, 7.35, 7.6))), "");
        set("centre3", easeInOut(centreIn) * easeInOut(swap), "");

        var wash = seg(t, 7.55, 7.95);
        set("glow", 1 - easeInOut(wash), "");
        set("wash", easeInOut(wash), "");
        var introIn = seg(t, 8.0, 8.5);
        set("intro", easeInOut(introIn) * (1 - easeInOut(seg(t, 8.7, 9.0))),
            "scale(" + (0.86 + 0.14 * outExpo(introIn)) + ")");
        set("tick", easeInOut(introIn) * (1 - easeInOut(seg(t, 8.7, 9.0))),
            "scale(" + (0.7 + 0.3 * outExpo(introIn)) + ")");
        var stackIn = seg(t, 8.6, 9.15);
        var stackOut = seg(t, 11.0, 11.4);
        var stackAlpha = easeInOut(stackIn) * (1 - easeInOut(stackOut));
        set("stack", stackAlpha, "");
        set("stackTop", stackAlpha, "");
        set("stackWhite", easeInOut(seg(t, 9.8, 10.3)) * (1 - easeInOut(stackOut)), "");
        set("stackSub", easeInOut(seg(t, 10.2, 10.6)) * (1 - easeInOut(stackOut)), "");
        set("stackBlack", easeInOut(seg(t, 10.5, 10.9)) * (1 - easeInOut(stackOut)), "");

        var badgeIn = seg(t, 11.7, 12.4);
        var badgeOut = seg(t, 12.9, 13.3);
        set("badge", easeInOut(badgeIn) * (1 - easeInOut(badgeOut)),
            "scale(" + (0.2 + 0.8 * outBack(badgeIn)) + ")");
        set("badgeText", easeInOut(seg(t, 11.9, 12.4)) * (1 - easeInOut(badgeOut)), "");

        var contactIn = seg(t, 12.9, 13.5);
        var contactOut = seg(t, 15.0, 15.3);
        var contactAlpha = easeInOut(contactIn) * (1 - easeInOut(contactOut));
        set("contact", contactAlpha, "");
        set("contactChip", contactAlpha, "");
        set("phones", easeInOut(seg(t, 13.2, 13.7)) * (1 - easeInOut(contactOut)), "");
        set("site", easeInOut(seg(t, 13.45, 13.85)) * (1 - easeInOut(contactOut)), "");
        set("handles", easeInOut(seg(t, 13.7, 14.1)) * (1 - easeInOut(contactOut)), "");

        set("endCard", seg(t, 15.2, 15.5), "");
    };

    window.seek(window.__OMNIFRAME_FRAME__ / window.__OMNIFRAME_FPS__);
})();

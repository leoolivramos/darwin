package com.leonardoramos.app.controller;

import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

import java.util.Random;

@RestController
public class PerformanceController {

    private final Random random = new Random();

    @GetMapping("/hello")
    public String hello() {
        return "Darwin online";
    }

    @GetMapping("/process")
    public String processData(String input) {
        return input.toUpperCase();
    }

    @GetMapping("/slow")
    public String simulateSlow() throws InterruptedException {
        int delay = 1000 + random.nextInt(3000);
        Thread.sleep(delay);
        return "Processo concluído após " + delay + "ms";
    }

    @PostMapping("/compute")
    public int computeSum(int a, int b) {
        return a + b;
    }
}

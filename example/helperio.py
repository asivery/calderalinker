postconstruct("""
        this.emulator.v86.cpu.io.register_write(0xFF, this.emulator.v86.cpu, function(data) {
            let line = "", char;
            data = this.reg32[0];
            while((char = this.mem8[data++]) !== 0) {
                line += String.fromCharCode(char);
            }
            console.log("SYSTEM:", line);
        });

        this.emulator.v86.cpu.io.register_write(0xFE, this.emulator.v86.cpu, function(data) {
            data = this.reg32[0];
            console.log("SYSTEM (Number):", data);
        });
""")

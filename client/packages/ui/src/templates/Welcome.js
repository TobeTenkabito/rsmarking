export const WelcomeTemplate = `
<div id="welcome-screen" class="fixed inset-0 z-[2000] bg-[#030712] overflow-hidden font-sans">
    <canvas id="stardust-canvas" class="absolute inset-0 w-full h-full"></canvas>

    <div class="absolute inset-0 bg-[radial-gradient(circle_at_center,transparent_0%,#030712_100%)] pointer-events-none"></div>

    <div class="absolute inset-0 z-10 flex flex-col items-center justify-center pointer-events-none">
        <!-- Logo 区域：渐变色加入紫色呼应背景 -->
        <div class="relative w-48 h-48 mb-6 flex items-center justify-center group pointer-events-auto">
            <div id="aggr-logo" class="relative z-10 text-6xl text-transparent bg-clip-text bg-gradient-to-br from-cyan-400 via-purple-400 to-blue-500 font-black tracking-[0.1em] uppercase drop-shadow-[0_0_15px_rgba(168,85,247,0.4)] transition-transform duration-700 group-hover:scale-110">
                RS
            </div>
            
            <div class="absolute inset-0 border-[1px] border-cyan-500/30 rounded-full animate-[spin_10s_linear_infinite]"></div>
            <div class="absolute inset-2 border-[1px] border-purple-500/40 rounded-full animate-[spin_15s_linear_infinite_reverse] border-dashed"></div>
            <div class="absolute inset-[-20px] bg-cyan-500/5 rounded-full blur-xl group-hover:bg-purple-500/10 transition-colors duration-700"></div>
        </div>

        <!-- 标题区域 -->
        <div class="text-center mb-16 pointer-events-auto">
            <h1 class="text-5xl font-black text-white tracking-[0.15em] mb-4 uppercase drop-shadow-lg">
                RSMarking <span class="text-transparent bg-clip-text bg-gradient-to-r from-cyan-400 to-purple-500">Pro</span>
            </h1>
            <div class="flex items-center justify-center gap-4">
                <div class="h-[1px] w-12 bg-gradient-to-r from-transparent to-cyan-500/50"></div>
                <p class="text-cyan-100/70 text-sm tracking-[0.4em] font-medium">INTELLIGENT REMOTE SENSING AGENT</p>
                <div class="h-[1px] w-12 bg-gradient-to-l from-transparent to-cyan-500/50"></div>
            </div>
        </div>

        <!-- 按钮区域 -->
        <button id="btn-enter-system" class="pointer-events-auto group relative px-10 py-4 overflow-hidden rounded-none border border-cyan-500/30 bg-cyan-950/20 hover:bg-purple-900/30 backdrop-blur-sm transition-all duration-500">
            <div class="absolute inset-0 -translate-x-full bg-gradient-to-r from-transparent via-cyan-400/20 to-transparent group-hover:animate-[shimmer_1.5s_infinite]"></div>
            
            <div class="absolute top-0 left-0 w-2 h-2 border-t border-l border-cyan-400"></div>
            <div class="absolute top-0 right-0 w-2 h-2 border-t border-r border-cyan-400"></div>
            <div class="absolute bottom-0 left-0 w-2 h-2 border-b border-l border-cyan-400"></div>
            <div class="absolute bottom-0 right-0 w-2 h-2 border-b border-r border-cyan-400"></div>

            <span class="relative text-cyan-300 group-hover:text-white text-sm font-bold tracking-[0.3em] transition-colors duration-300">
                INITIALIZE SYSTEM
            </span>
        </button>
    </div>

    <style>
        @keyframes shimmer {
            100% { transform: translateX(100%); }
        }
        #welcome-screen {
            transition: opacity 1s ease-in-out, filter 1s ease-in-out;
        }
        #welcome-screen.exit-active {
            opacity: 0;
            filter: blur(20px) brightness(2);
            pointer-events: none;
        }
        #welcome-screen.exit-active #stardust-canvas {
            transform: scale(1.5);
            transition: transform 1.5s cubic-bezier(0.1, 0.8, 0.3, 1);
        }
    </style>
</div>
`;

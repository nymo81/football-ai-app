<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Football AI</title>
    <script src="https://cdn.tailwindcss.com"></script>
</head>
<body class="bg-gray-900 text-white min-h-screen p-6">
    <div class="max-w-6xl mx-auto">
        <header class="text-center mb-12">
            <h1 class="text-4xl font-bold text-green-400 tracking-wider">AI FOOTBALL PREDICTIONS</h1>
            <p class="text-gray-400 mt-2">Powered by Python & Laravel</p>
        </header>

        <div class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
            @foreach($matches as $match)
            <div class="bg-gray-800 rounded-xl border border-gray-700 shadow-lg overflow-hidden hover:border-green-500 transition duration-300">
                <div class="p-6 text-center border-b border-gray-700">
                    <div class="text-xl font-bold flex justify-between items-center">
                        <span class="w-1/3 text-right">{{ $match->home_team }}</span>
                        <span class="text-gray-500 text-sm px-2">VS</span>
                        <span class="w-1/3 text-left">{{ $match->away_team }}</span>
                    </div>
                </div>
                <div class="p-4 bg-black/50 text-center">
                    <p class="text-xs text-gray-500 uppercase tracking-wide mb-1">AI Prediction</p>
                    <p class="text-2xl font-extrabold text-green-400">{{ $match->prediction }}</p>
                    <div class="mt-2 inline-block px-3 py-1 rounded-full text-xs font-bold bg-gray-700">
                        {{ $match->confidence }}% Confidence
                    </div>
                </div>
            </div>
            @endforeach
        </div>
    </div>
</body>
</html>

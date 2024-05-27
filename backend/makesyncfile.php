<?php
// configuration
// server domain
$servername = "localhost";
// enable https
$https = false;

if ($argc != 2) {
    echo "Usage: php makesyncfile.php <subdirectory>\n";
    exit(1);
}

$subdirectory = $argv[1];

if (!is_dir($subdirectory)) {
    echo "The provided path is not a valid directory.\n";
    exit(1);
}

$fileList = [];

function getFileList($dir, $baseDir) {
    global $fileList;
    global $subdirectory;
    global $servername;
    global $https;
    
    $files = scandir($dir);
    foreach ($files as $file) {
        if ($file === '.' || $file === '..') {
            continue;
        }
        $fullPath = $dir . DIRECTORY_SEPARATOR . $file;
        if (is_dir($fullPath)) {
            getFileList($fullPath, $baseDir);
        } else {
            $fileDetail['name'] = $file;
            $fileDetail['path'] = str_replace([$baseDir . DIRECTORY_SEPARATOR, '/'], ['', '\\'], $fullPath);
            $fileDetail['link'] = "http" . ($https ? 's' : '') . "://$servername/$subdirectory/" . str_replace($baseDir . DIRECTORY_SEPARATOR, '', $fullPath);
            $fileList[] = $fileDetail;
        }
    }
}

getFileList($subdirectory, $subdirectory);

$outputFile = "$subdirectory.json";
file_put_contents($outputFile, json_encode($fileList, JSON_PRETTY_PRINT));

echo "File tree has been saved to $outputFile\n";

?>
